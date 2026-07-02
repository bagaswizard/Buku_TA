#include <geometry_msgs/PoseWithCovarianceStamped.h>
#include <geometry_msgs/TransformStamped.h>
#include <std_msgs/Empty.h>
#include <std_msgs/Char.h>
#include <std_msgs/Bool.h>
#include <std_msgs/Float64MultiArray.h>
#include <sensor_msgs/Imu.h>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2/LinearMath/Matrix3x3.h>
#include <nav_msgs/OccupancyGrid.h>
#include <geometry_msgs/Twist.h>
#include <visualization_msgs/MarkerArray.h>
#include <ros/ros.h>
#include <tf2_ros/transform_listener.h>
#include <tf2_ros/buffer.h>
#include <yaml-cpp/yaml.h>
#include <costmap_2d/costmap_2d.h>
#include <costmap_2d/cost_values.h>

#include <algorithm>
#include <cmath>
#include <map>
#include <cstring>
#include <limits>
#include <queue>
#include <set>
#include <string>
#include <vector>
#include <utility>

namespace
{
    // Internal costmap values (used by transition layer internally)
    const unsigned char COST_TRANSITION_EXPANSION = 5;
    const unsigned char COST_TRANSITION_MAIN_DATA = 1;
    const unsigned char COST_TRANSITION_LETHAL = 1;

    // OccupancyGrid values (from costmap_2d_publisher cost_translation_table_):
    //   internal 1 -> OG 1  (main/lethal)
    //   internal 5 -> OG 2  (expansion)
    const unsigned char OG_TRANSITION_MIN = 1;
    const unsigned char OG_TRANSITION_MAIN = 2;

    inline bool isTransitionCost(unsigned char c)
    {
        return c >= OG_TRANSITION_MIN && c <= OG_TRANSITION_MAIN;
    }

    inline bool hasTransitionData(const unsigned char* data, int count)
    {
        for (int i = 0; i < count; ++i) {
            if (data[i] >= OG_TRANSITION_MIN && data[i] <= OG_TRANSITION_MAIN)
                return true;
        }
        return false;
    }

    struct Pixel
    {
        int x;
        int y;
    };

    struct TransitionPair
    {
        int pair_id;
        Pixel seed_A;
        Pixel seed_B;
        double awx, awy;               // world coords for seed_A (region tracking)
        double bwx, bwy;               // world coords for seed_B
        double cx_A, cy_A;           // OG-1 centroids (for path_interceptor)
        double cx_B, cy_B;
        double cx_A_exp, cy_A_exp;   // OG-2 centroids (for jumping)
        double cx_B_exp, cy_B_exp;
        bool traced;
    };
} // namespace

class CostmapJumperNode
{
public:
    CostmapJumperNode()
        : nh_(), private_nh_("~"), tf_buffer_(), tf_listener_(tf_buffer_)
    {
        loadYaml();
        loadInitialPoseParam();
        loadRegionOrientations();
        convertInitialPose();

        startup_time_ = ros::Time::now();
        private_nh_.param("base_frame", base_frame_, std::string("base_link"));
        private_nh_.param("check_rate", check_rate_, 20.0);
        private_nh_.param("pair_cooldown", pair_cooldown_duration_, 5.0);
        private_nh_.param("initial_jump_delay", initial_jump_delay_, 5.0);
        private_nh_.param("enable_waiting", enable_waiting_, true);
        private_nh_.param("jump_pose_duration", jump_pose_duration_, 1.0);
        private_nh_.param("costmap_topic", costmap_topic_,
                          std::string("/transition_costmap/costmap/costmap"));
        nh_.param("/transition_costmap/costmap/transition_expansion_layer/expansion_radius", expansion_radius_, 0.45);
        private_nh_.param("pitch_jump_enable", pitch_jump_enabled_, true);
        private_nh_.param("pitch_jump_threshold", pitch_threshold_, 12.0);
        pitch_threshold_ = pitch_threshold_ * M_PI / 180.0;

        initial_pose_pub_ = nh_.advertise<geometry_msgs::PoseWithCovarianceStamped>("/initialpose", 1, true);
        transition_jumped_pub_ = nh_.advertise<std_msgs::Empty>("/transition_jumped", 1, true);
        transition_marker_pub_ = nh_.advertise<visualization_msgs::MarkerArray>("/transition_labels", 1, true);
        region_pub_ = nh_.advertise<std_msgs::Char>("/current_region", 1, true);
        centroid_pub_ = nh_.advertise<std_msgs::Float64MultiArray>("/transition_centroids", 1, true);
        toggle_icp_pub_ = nh_.advertise<std_msgs::Bool>("/icp_loc_node/toggle_icp", 1);
        transition_vel_pub_ = nh_.advertise<std_msgs::Bool>("transition_vel", 1);
        costmap_sub_ = nh_.subscribe(costmap_topic_, 1, &CostmapJumperNode::costmapCallback, this);
        cmd_vel_sub_ = nh_.subscribe("/cmd_vel", 1, &CostmapJumperNode::cmdVelCallback, this);
        imu_sub_ = nh_.subscribe("/imu/data", 1, &CostmapJumperNode::imuCallback, this);

        publish_initial_pose_timer_ = nh_.createTimer(
            ros::Duration(0.5),
            &CostmapJumperNode::publishInitialPose,
            this, false);

        check_timer_ = nh_.createTimer(
            ros::Duration(1.0 / check_rate_),
            &CostmapJumperNode::checkTimerCallback,
            this);

        ROS_INFO("costmap_jumper: started");
    }

private:
    // ----------------------------------------------------------------
    // YAML loading
    // ----------------------------------------------------------------

    void loadYaml()
    {
        std::string yaml_path;
        private_nh_.param("transition_pairs_yaml", yaml_path, std::string(""));

        if (yaml_path.empty())
        {
            ROS_FATAL("costmap_jumper: required param 'transition_pairs_yaml' not set");
            return;
        }

        if (!loadYamlFile(yaml_path))
        {
            ROS_FATAL_STREAM("costmap_jumper: failed to load YAML " << yaml_path);
            return;
        }

        ROS_INFO_STREAM("costmap_jumper: loaded YAML origin ["
                        << yaml_origin_x_ << ", " << yaml_origin_y_
                        << "]  resolution " << yaml_resolution_);
    }

    bool loadYamlFile(const std::string &path)
    {
        YAML::Node doc;
        try
        {
            doc = YAML::LoadFile(path);
        }
        catch (const std::exception &e)
        {
            ROS_ERROR_STREAM("costmap_jumper: YAML parse error: " << e.what());
            return false;
        }

        if (doc["resolution"])
            yaml_resolution_ = doc["resolution"].as<double>();

        if (doc["origin"] && doc["origin"].IsSequence() && doc["origin"].size() >= 2)
        {
            yaml_origin_x_ = doc["origin"][0].as<double>();
            yaml_origin_y_ = doc["origin"][1].as<double>();
        }

        if (doc["initial_pose"] && doc["initial_pose"].IsSequence() && doc["initial_pose"].size() >= 2)
        {
            initial_pose_pixel_x_ = doc["initial_pose"][0].as<double>();
            initial_pose_pixel_y_ = doc["initial_pose"][1].as<double>();
        }

        const YAML::Node &transitions = doc["transitions"];
        if (!transitions || !transitions.IsSequence())
        {
            ROS_WARN("costmap_jumper: no 'transitions' array in YAML");
            return true;
        }

        for (std::size_t i = 0; i < transitions.size(); ++i)
        {
            const YAML::Node &t = transitions[i];

            if (!t["first_pixel_A"] || !t["first_pixel_B"])
            {
                ROS_WARN_STREAM("costmap_jumper: skipping entry " << i << " -- missing pixel fields");
                continue;
            }

            TransitionPair p;
            p.pair_id = t["pair"] ? t["pair"].as<int>() : static_cast<int>(i);
            p.traced = false;

            p.seed_A = {
                t["first_pixel_A"][0].as<int>(),
                t["first_pixel_A"][1].as<int>()};
            p.seed_B = {
                t["first_pixel_B"][0].as<int>(),
                t["first_pixel_B"][1].as<int>()};

            p.awx = yaml_origin_x_ + p.seed_A.x * yaml_resolution_;
            p.awy = -(yaml_origin_y_ + p.seed_A.y * yaml_resolution_);
            p.bwx = yaml_origin_x_ + p.seed_B.x * yaml_resolution_;
            p.bwy = -(yaml_origin_y_ + p.seed_B.y * yaml_resolution_);

            transition_pairs_.push_back(p);

            ROS_INFO_STREAM("costmap_jumper: pair " << p.pair_id
                                                    << "  A[" << p.seed_A.x << "," << p.seed_A.y << "]"
                                                    << "  B[" << p.seed_B.x << "," << p.seed_B.y << "]");
        }

        if (doc["region_orientations"])
        {
            for (const auto &entry : doc["region_orientations"])
            {
                std::string key = entry.first.as<std::string>();
                if (key.empty())
                    continue;
                char region = key[0];
                const auto &q = entry.second;
                geometry_msgs::Quaternion quat;
                quat.x = q["x"].as<double>(0.0);
                quat.y = q["y"].as<double>(0.0);
                quat.z = q["z"].as<double>(0.0);
                quat.w = q["w"].as<double>(1.0);
                region_orientations_[region] = quat;
                ROS_INFO_STREAM("costmap_jumper: orientation override for region "
                                << region << " = [" << quat.x << "," << quat.y
                                << "," << quat.z << "," << quat.w << "]");
            }
        }

        return true;
    }

    void loadInitialPoseParam()
    {
        private_nh_.param("initial_pose_z", initial_pose_z_, 0.0);
        private_nh_.param("initial_pose_yaw", initial_pose_yaw_, 0.0);
        private_nh_.param("initial_pose_qx", initial_pose_qx_, 0.0);
        private_nh_.param("initial_pose_qy", initial_pose_qy_, 0.0);
        private_nh_.param("initial_pose_qz", initial_pose_qz_, 0.0);
        private_nh_.param("initial_pose_qw", initial_pose_qw_, 1.0);

        private_nh_.param("initial_pose_pixel_x", initial_pose_pixel_x_, initial_pose_pixel_x_);
        private_nh_.param("initial_pose_pixel_y", initial_pose_pixel_y_, initial_pose_pixel_y_);
    }

    void loadRegionOrientations()
    {
        XmlRpc::XmlRpcValue regions;
        if (!private_nh_.getParam("region_orientations", regions))
            return;

        for (auto it = regions.begin(); it != regions.end(); ++it)
        {
            std::string key = it->first;
            if (key.size() != 1) continue;
            char region = key[0];
            auto val = it->second;
            geometry_msgs::Quaternion q;
            q.x = val.hasMember("x") ? static_cast<double>(val["x"]) : 0.0;
            q.y = val.hasMember("y") ? static_cast<double>(val["y"]) : 0.0;
            q.z = val.hasMember("z") ? static_cast<double>(val["z"]) : 0.0;
            q.w = val.hasMember("w") ? static_cast<double>(val["w"]) : 1.0;
            region_orientations_[region] = q;
            ROS_INFO("costmap_jumper: orientation delta for region %c = [%.3f, %.3f, %.3f, %.3f]",
                     region, q.x, q.y, q.z, q.w);
        }
    }

    // ----------------------------------------------------------------
    // Costmap reception & line tracing
    // ----------------------------------------------------------------

    void costmapCallback(const nav_msgs::OccupancyGridConstPtr &msg)
    {
        cm_.resizeMap(msg->info.width, msg->info.height,
                      msg->info.resolution,
                      msg->info.origin.position.x,
                      msg->info.origin.position.y);
        std::memcpy(cm_.getCharMap(), msg->data.data(), msg->data.size());

        if (!cm_received_)
        {
            ROS_INFO_STREAM("costmap_jumper: costmap received "
                            << cm_.getSizeInCellsX() << "x" << cm_.getSizeInCellsY()
                            << "  origin [" << cm_.getOriginX() << "," << cm_.getOriginY()
                            << "]  res " << cm_.getResolution());
            diagnoseTransitionCosts();
            transition_last_diag_ = ros::Time::now();
        }

        cm_received_ = true;

        int total = cm_.getSizeInCellsX() * cm_.getSizeInCellsY();
        if (hasTransitionData(cm_.getCharMap(), total))
        {
            if (!traced_)
            {
                ROS_INFO("costmap_jumper: transition data detected -- tracing lines");
                traced_ = true;
            }
            traceAllLines();
            publishTransitionMarkers();
        }
        else
        {
            double elapsed = (ros::Time::now() - transition_last_diag_).toSec();
            if (elapsed > 10.0)
            {
                diagnoseTransitionCosts();
                transition_last_diag_ = ros::Time::now();
            }
        }

        if (!initial_pose_published_)
        {
            convertInitialPose();
            publishInitialPose(ros::TimerEvent());
        }
    }

    void cmdVelCallback(const geometry_msgs::Twist::ConstPtr &msg)
    {
        last_cmd_vel_ = *msg;
    }

    void convertInitialPose()
    {
        if (initial_pose_x_converted_)
            return;

        double mx = yaml_origin_x_ + initial_pose_pixel_x_ * yaml_resolution_;
        double my = -(yaml_origin_y_ + initial_pose_pixel_y_ * yaml_resolution_);
        initial_pose_x_ = mx;
        initial_pose_y_ = my;
        initial_pose_x_converted_ = true;

        ROS_INFO_STREAM("costmap_jumper: initial_pose converted from pixels ["
                        << initial_pose_pixel_x_ << "," << initial_pose_pixel_y_
                        << "] to map [" << mx << "," << my << "]");
    }

    void traceAllLines()
    {
        const int WINDOW = 80;
        unsigned int sx = cm_.getSizeInCellsX(), sy = cm_.getSizeInCellsY();

        for (auto &pair : transition_pairs_)
        {
            int ciA = yamlToCellI(pair.seed_A.x);
            int cjA = yamlToCellJ(pair.seed_A.y);
            int ciB = yamlToCellI(pair.seed_B.x);
            int cjB = yamlToCellJ(pair.seed_B.y);

            double s1x = 0, s1y = 0, s2x = 0, s2y = 0;
            int c1 = 0, c2 = 0;

            for (int dx = -WINDOW; dx <= WINDOW; ++dx)
                for (int dy = -WINDOW; dy <= WINDOW; ++dy)
                {
                    int nx = ciA + dx, ny = cjA + dy;
                    if (nx < 0 || nx >= (int)sx || ny < 0 || ny >= (int)sy) continue;
                    auto c = cm_.getCost(nx, ny);
                    if (c == OG_TRANSITION_MIN) {
                        double wx, wy; cm_.mapToWorld(nx, ny, wx, wy);
                        s1x += wx; s1y += wy; c1++;
                    } else if (c == OG_TRANSITION_MAIN) {
                        double wx, wy; cm_.mapToWorld(nx, ny, wx, wy);
                        s2x += wx; s2y += wy; c2++;
                    }
                }
            pair.cx_A = c1 ? s1x / c1 : 0;
            pair.cy_A = c1 ? s1y / c1 : 0;
            pair.cx_A_exp = c2 ? s2x / c2 : 0;
            pair.cy_A_exp = c2 ? s2y / c2 : 0;
            int cnt_A1 = c1, cnt_A2 = c2;

            s1x = s1y = s2x = s2y = 0; c1 = c2 = 0;
            for (int dx = -WINDOW; dx <= WINDOW; ++dx)
                for (int dy = -WINDOW; dy <= WINDOW; ++dy)
                {
                    int nx = ciB + dx, ny = cjB + dy;
                    if (nx < 0 || nx >= (int)sx || ny < 0 || ny >= (int)sy) continue;
                    auto c = cm_.getCost(nx, ny);
                    if (c == OG_TRANSITION_MIN) {
                        double wx, wy; cm_.mapToWorld(nx, ny, wx, wy);
                        s1x += wx; s1y += wy; c1++;
                    } else if (c == OG_TRANSITION_MAIN) {
                        double wx, wy; cm_.mapToWorld(nx, ny, wx, wy);
                        s2x += wx; s2y += wy; c2++;
                    }
                }
            pair.cx_B = c1 ? s1x / c1 : 0;
            pair.cy_B = c1 ? s1y / c1 : 0;
            pair.cx_B_exp = c2 ? s2x / c2 : 0;
            pair.cy_B_exp = c2 ? s2y / c2 : 0;
            int cnt_B1 = c1, cnt_B2 = c2;

            pair.traced = (cnt_A1 > 0 && cnt_B1 > 0);

            ROS_INFO_STREAM("costmap_jumper: pair " << pair.pair_id
                            << "  seed_A OG1=" << cnt_A1 << " OG2=" << cnt_A2
                            << "  seed_B OG1=" << cnt_B1 << " OG2=" << cnt_B2
                            << "  traced=" << (pair.traced ? "yes" : "no"));
            if (pair.traced)
                ROS_INFO_STREAM("costmap_jumper: pair " << pair.pair_id
                                << "  OG1 A(" << pair.cx_A << "," << pair.cy_A << ")"
                                << " B(" << pair.cx_B << "," << pair.cy_B << ")"
                                << "  OG2 A(" << pair.cx_A_exp << "," << pair.cy_A_exp << ")"
                                << " B(" << pair.cx_B_exp << "," << pair.cy_B_exp << ")");
        }
        publishCentroids();

        bool any_traced = false;
        for (const auto &p : transition_pairs_)
            if (p.traced) { any_traced = true; break; }
        if (!any_traced && cm_.getSizeInCellsX() > 0)
            diagnoseTransitionCosts();
    }

    void diagnoseTransitionCosts()
    {
        unsigned int sx = cm_.getSizeInCellsX(), sy = cm_.getSizeInCellsY();
        int total = static_cast<int>(sx) * static_cast<int>(sy);
        if (total == 0)
            return;
        int histogram[256] = {0};
        const unsigned char *data = cm_.getCharMap();
        for (int i = 0; i < total; ++i)
            ++histogram[data[i]];
        ROS_INFO_STREAM("costmap_jumper: diag  total=" << total);
        for (int v = 0; v < 256; ++v)
        {
            if (histogram[v] > 0)
                ROS_INFO_STREAM("costmap_jumper: diag  cost[" << v << "]=" << histogram[v]);
        }
    }

    // ----------------------------------------------------------------
    // Transition label markers
    // ----------------------------------------------------------------

    void publishTransitionMarkers()
    {
        if (!cm_received_)
            return;

        visualization_msgs::MarkerArray markers;
        int marker_id = 0;

        for (const auto &pair : transition_pairs_)
        {
            if (!pair.traced)
                continue;

            int side = 0;
            for (double cx : {pair.cx_A, pair.cx_B})
            {
                double cy = (side == 0) ? pair.cy_A : pair.cy_B;
                if (cx == 0 && cy == 0) { ++side; continue; }

                char letter = 'A' + pair.pair_id + side;

                visualization_msgs::Marker marker;
                marker.header.frame_id = "map";
                marker.header.stamp = ros::Time::now();
                marker.ns = "transition_labels";
                marker.id = marker_id++;
                marker.type = visualization_msgs::Marker::TEXT_VIEW_FACING;
                marker.action = visualization_msgs::Marker::ADD;
                marker.pose.position.x = cx;
                marker.pose.position.y = cy;
                marker.pose.position.z = 0.5;
                marker.pose.orientation.w = 1.0;
                marker.scale.z = 0.4;
                marker.color.a = 1.0;
                marker.color.r = 1.0;
                marker.color.g = 1.0;
                marker.color.b = 1.0;
                marker.text = std::string(1, letter);

                markers.markers.push_back(marker);
                ++side;
            }
        }

        transition_marker_pub_.publish(markers);
    }

    // ----------------------------------------------------------------
    // IMU callback - pitch tracking
    // ----------------------------------------------------------------

    void imuCallback(const sensor_msgs::Imu::ConstPtr &msg)
    {
        tf2::Quaternion q(msg->orientation.x, msg->orientation.y,
                          msg->orientation.z, msg->orientation.w);
        tf2::Matrix3x3 m(q);
        double roll, pitch, yaw;
        m.getRPY(roll, pitch, yaw);
        pitch_current_ = pitch;
    }

    // ----------------------------------------------------------------
    // TF timer callback - detection & jump
    // ----------------------------------------------------------------

    void checkTimerCallback(const ros::TimerEvent &)
    {
        if (!cm_received_)
            return;
        if (transition_pairs_.empty())
            return;

        // Robot pose from TF
        geometry_msgs::TransformStamped robot_tf;
        try
        {
            robot_tf = tf_buffer_.lookupTransform("map", base_frame_, ros::Time(0));
        }
        catch (tf2::TransformException &)
        {
            return;
        }

        double rx = robot_tf.transform.translation.x;
        double ry = robot_tf.transform.translation.y;

        // Continuously track region based on TF position
        char r = regionOfPoint(rx, ry);
        if (r != current_region_)
        {
            ROS_INFO("costmap_jumper: region changed '%c' -> '%c'", current_region_, r);
            current_region_ = r;
            publishRegion();
        }

        // Costmap cell
        unsigned int ci, cj;
        if (!cm_.worldToMap(rx, ry, ci, cj))
            return;

        unsigned char cost = cm_.getCost(ci, cj);
        double elapsed = (ros::Time::now() - startup_time_).toSec();
        // ROS_INFO("costmap_jumper: robot at cell [%u,%u] world [%.3f,%.3f] cost=%d  elapsed=%.1fs",
        //          ci, cj, rx, ry, static_cast<int>(cost), elapsed);

        // Startup grace period -- suppress jumps for initial_jump_delay_ seconds
        if (elapsed < initial_jump_delay_)
            return;

        // Wait until initial pose has been applied by ICP
        if (!initial_pose_published_)
            return;
        double pose_age = (ros::Time::now() - initial_pose_pub_time_).toSec();
        if (pose_age < 3.0)
            return;

        // Verify robot is near the expected initial pose (confirms ICP applied it)
        double dist_from_init = std::hypot(rx - initial_pose_x_, ry - initial_pose_y_);
        if (dist_from_init > 1.5 && jump_count_ == 0)
        {
            ROS_DEBUG("costmap_jumper: skipping jump -- robot %.2fm from initial pose (ICP may not have applied it)",
                      dist_from_init);
            return;
        }

        // Cooldown check
        if (jump_cooldown_ > 0.0)
        {
            double cooldown_elapsed = (ros::Time::now() - last_jump_stamp_).toSec();
            if (cooldown_elapsed < jump_cooldown_)
                return;
        }

        Pixel transition_pixel;
        bool found = false;

        if (isTransitionCost(cost))
        {
            transition_pixel = {static_cast<int>(ci), static_cast<int>(cj)};
            found = true;

            if (enable_waiting_)
            {
                // ---- Match pair/side BEFORE starting wait ----
                pending_pair_id_ = -1;
                pending_side_a_ = true;
                int best_d2 = std::numeric_limits<int>::max();

                for (const auto &pair : transition_pairs_)
                {
                    int ax = yamlToCellI(pair.seed_A.x);
                    int ay = yamlToCellJ(pair.seed_A.y);
                    int da = (ax - transition_pixel.x) * (ax - transition_pixel.x) +
                             (ay - transition_pixel.y) * (ay - transition_pixel.y);

                    int bx = yamlToCellI(pair.seed_B.x);
                    int by = yamlToCellJ(pair.seed_B.y);
                    int db = (bx - transition_pixel.x) * (bx - transition_pixel.x) +
                             (by - transition_pixel.y) * (by - transition_pixel.y);

                    if (da < best_d2) { best_d2 = da; pending_pair_id_ = pair.pair_id; pending_side_a_ = true; }
                    if (db < best_d2) { best_d2 = db; pending_pair_id_ = pair.pair_id; pending_side_a_ = false; }
                }

                if (pending_pair_id_ < 0)
                    return;

                // ---- Block wait if this pair is on cooldown ----
                auto ct = pair_cooldown_end_.find(pending_pair_id_);
                if (ct != pair_cooldown_end_.end() && ros::Time::now() < ct->second)
                {
                    if (waiting_for_jump_)
                    {
                        std_msgs::Bool umsg; umsg.data = true;
                        toggle_icp_pub_.publish(umsg);
                        std_msgs::Bool vmsg; vmsg.data = false;
                        transition_vel_pub_.publish(vmsg);
                        waiting_for_jump_ = false;
                    }
                    return;
                }

                // ---- Waiting state machine ----
                if (waiting_for_jump_)
                {
                    if (pitch_jump_enabled_ &&
                        std::fabs(pitch_current_ - pitch_baseline_) >= pitch_threshold_)
                    {
                        ROS_INFO("costmap_jumper: jump triggered by pitch (delta=%.1f deg)",
                                 std::fabs(pitch_current_ - pitch_baseline_) * 180.0 / M_PI);
                        executeJump(transition_pixel, pending_pair_id_, pending_side_a_,
                                    robot_tf.transform.rotation, rx, ry);
                        return;
                    }

                    double waited = (ros::Time::now() - wait_start_time_).toSec();
                    if (waited < jump_wait_duration_)
                    {
                        if ((ros::Time::now() - last_countdown_log_).toSec() >= 1.0)
                        {
                            ROS_INFO("costmap_jumper: waiting... %.0fs remaining", jump_wait_duration_ - waited);
                            last_countdown_log_ = ros::Time::now();
                        }
                        return;
                    }
                }
                else
                {
                    double speed = std::hypot(last_cmd_vel_.linear.x, last_cmd_vel_.linear.y);
                    if (speed < 0.05) speed = 0.05;
                    jump_wait_duration_ = 2.0 * expansion_radius_ / speed;
                    wait_start_time_ = ros::Time::now();
                    last_countdown_log_ = wait_start_time_;
                    waiting_for_jump_ = true;
                    pitch_baseline_ = pitch_current_;

                    std_msgs::Bool vmsg;
                    vmsg.data = true;
                    transition_vel_pub_.publish(vmsg);

                    std_msgs::Bool fmsg;
                    fmsg.data = false;
                    toggle_icp_pub_.publish(fmsg);

                    ROS_INFO("costmap_jumper: transition zone reached, waiting %.2fs (speed=%.3f, radius=%.2f, 2x)",
                             jump_wait_duration_, speed, expansion_radius_);
                    return;
                }
            }
        }
        else
        {
            if (waiting_for_jump_)
            {
                std_msgs::Bool umsg;
                umsg.data = true;
                toggle_icp_pub_.publish(umsg);
                std_msgs::Bool vmsg; vmsg.data = false;
                transition_vel_pub_.publish(vmsg);
                waiting_for_jump_ = false;
            }
        }

        if (!found)
        {
            ROS_DEBUG_STREAM("costmap_jumper: robot at cell [" << ci << "," << cj
                                                               << "] cost=" << static_cast<int>(cost) << " -- no transition found");
            return;
        }

        ROS_INFO_STREAM_THROTTLE(1.0, "costmap_jumper: robot at cell [" << ci << "," << cj
                                                                        << "] cost=" << static_cast<int>(cost)
                                                                        << "  transition pixel [" << transition_pixel.x << "," << transition_pixel.y << "]");

        // ---- Identify which pair / side (for non-waiting path or after wait expires) ----
        int pair_id;
        bool on_side_A;
        if (enable_waiting_)
        {
            pair_id = pending_pair_id_;
            on_side_A = pending_side_a_;
        }
        else
        {
            pair_id = -1;
            on_side_A = true;
            int best_d2 = std::numeric_limits<int>::max();
            for (const auto &pair : transition_pairs_)
            {
                int ax = yamlToCellI(pair.seed_A.x);
                int ay = yamlToCellJ(pair.seed_A.y);
                int da = (ax - transition_pixel.x) * (ax - transition_pixel.x) +
                         (ay - transition_pixel.y) * (ay - transition_pixel.y);
                int bx = yamlToCellI(pair.seed_B.x);
                int by = yamlToCellJ(pair.seed_B.y);
                int db = (bx - transition_pixel.x) * (bx - transition_pixel.x) +
                         (by - transition_pixel.y) * (by - transition_pixel.y);
                if (da < best_d2) { best_d2 = da; pair_id = pair.pair_id; on_side_A = true; }
                if (db < best_d2) { best_d2 = db; pair_id = pair.pair_id; on_side_A = false; }
            }
            if (pair_id < 0) { ROS_WARN("costmap_jumper: no pair found"); return; }

            auto ct = pair_cooldown_end_.find(pair_id);
            if (ct != pair_cooldown_end_.end() && ros::Time::now() < ct->second)
            {
                ROS_DEBUG_STREAM("costmap_jumper: pair " << pair_id << " on cooldown -- skipping");
                return;
            }
        }

        if (pair_id < 0)
        {
            ROS_WARN("costmap_jumper: no pair found for transition pixel");
            return;
        }

        ROS_INFO_STREAM_THROTTLE(1.0, "costmap_jumper: matched pair " << pair_id
                                                                      << " side " << (on_side_A ? "A" : "B")
                                                                      << "  seed dist^2 ...");

        executeJump(transition_pixel, pair_id, on_side_A, robot_tf.transform.rotation, rx, ry);

        if (waiting_for_jump_)
        {
            std_msgs::Bool umsg;
            umsg.data = true;
            toggle_icp_pub_.publish(umsg);
            std_msgs::Bool vmsg; vmsg.data = false;
            transition_vel_pub_.publish(vmsg);
        }
        waiting_for_jump_ = false;
    }

    // ----------------------------------------------------------------
    // BFS nearest transition search (from expansion zone)
    // ----------------------------------------------------------------

    bool findNearestTransition(unsigned int start_i, unsigned int start_j, Pixel &out) const
    {
        const int dx8[] = {-1, -1, -1, 0, 0, 1, 1, 1};
        const int dy8[] = {-1, 0, 1, -1, 1, -1, 0, 1};
        unsigned int sx = cm_.getSizeInCellsX(), sy = cm_.getSizeInCellsY();

        std::queue<std::pair<int, int>> q;
        std::set<std::pair<int, int>> visited;
        q.push({static_cast<int>(start_i), static_cast<int>(start_j)});
        visited.insert({static_cast<int>(start_i), static_cast<int>(start_j)});

        const int max_dist = 200;

        while (!q.empty())
        {
            auto front = q.front();
            int cx = front.first;
            int cy = front.second;
            q.pop();

            if (isTransitionCost(cm_.getCost(cx, cy)))
            {
                out = {cx, cy};
                return true;
            }

            for (int d = 0; d < 8; ++d)
            {
                int nx = cx + dx8[d];
                int ny = cy + dy8[d];
                if (nx >= 0 && nx < static_cast<int>(sx) &&
                    ny >= 0 && ny < static_cast<int>(sy))
                {
                    auto key = std::make_pair(nx, ny);
                    if (visited.count(key))
                        continue;
                    unsigned char nc = cm_.getCost(nx, ny);
                    if (nc == 100 || nc == 255)
                        continue;
                    int dist = std::abs(nx - static_cast<int>(start_i)) + std::abs(ny - static_cast<int>(start_j));
                    if (dist > max_dist)
                        continue;
                    visited.insert(key);
                    q.push(key);
                }
            }
        }
        return false;
    }

    // ----------------------------------------------------------------
    // Jump execution
    // ----------------------------------------------------------------

    void executeJump(const Pixel &src_pixel, int pair_id, bool on_side_A,
                     const geometry_msgs::Quaternion &orientation,
                     double robot_x, double robot_y)
    {
        // Find the pair (try traced first, then fallback to untraced)
        const TransitionPair *pair_traced = nullptr;
        for (const auto &p : transition_pairs_)
        {
            if (p.pair_id == pair_id && p.traced)
            {
                pair_traced = &p;
                break;
            }
        }

        double dst_x, dst_y;
        if (pair_traced)
        {
            dst_x = on_side_A ? pair_traced->cx_B_exp : pair_traced->cx_A_exp;
            dst_y = on_side_A ? pair_traced->cy_B_exp : pair_traced->cy_A_exp;
        }
        else
        {
            const TransitionPair *p = nullptr;
            for (const auto &p2 : transition_pairs_) {
                if (p2.pair_id == pair_id) { p = &p2; break; }
            }
            if (!p) return;
            dst_x = on_side_A ? p->cx_B_exp : p->cx_A_exp;
            dst_y = on_side_A ? p->cy_B_exp : p->cy_A_exp;
        }

        ROS_INFO_STREAM("JUMP: "
                        << "pair " << pair_id
                        << "  side " << (on_side_A ? "A" : "B")
                        << "  dst=[" << dst_x << "," << dst_y << "]");

        // --- Compute destination-facing orientation ---
        geometry_msgs::Quaternion face_q;
        char dest_letter = 'A' + pair_id + (on_side_A ? 1 : 0);
        auto orient_it = region_orientations_.find(dest_letter);
        if (orient_it != region_orientations_.end())
        {
            tf2::Quaternion delta(orient_it->second.x, orient_it->second.y,
                                  orient_it->second.z, orient_it->second.w);
            tf2::Quaternion current(orientation.x, orientation.y,
                                    orientation.z, orientation.w);
            tf2::Quaternion result = delta * current;
            result.normalize();
            face_q.x = result.x(); face_q.y = result.y();
            face_q.z = result.z(); face_q.w = result.w();
        }
        else
        {
            face_q = orientation;
        }

        ROS_INFO_STREAM("JUMP: orientation " << face_q.x << " " << face_q.y << " "
                        << face_q.z << " " << face_q.w << " (dest_letter=" << dest_letter << ")");

        // --- Publish /initialpose with corrected orientation ---
        geometry_msgs::PoseWithCovarianceStamped pose_msg;
        pose_msg.header.stamp = ros::Time::now();
        pose_msg.header.frame_id = "map";
        pose_msg.pose.pose.position.x = dst_x;
        pose_msg.pose.pose.position.y = dst_y;
        pose_msg.pose.pose.position.z = initial_pose_z_;
        pose_msg.pose.pose.orientation = face_q;
        pose_msg.pose.covariance = {
            0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.06};

        initial_pose_pub_.publish(pose_msg);

        if (dest_letter == 'C')
        {
            int repeats = std::max(1, static_cast<int>(jump_pose_duration_));
            ros::Rate r(1);
            for (int i = 0; i < repeats; i++)
            {
                pose_msg.header.stamp = ros::Time::now();
                initial_pose_pub_.publish(pose_msg);
                r.sleep();
            }
        }

        transition_jumped_pub_.publish(std_msgs::Empty());

        last_jump_stamp_ = ros::Time::now();
        jump_count_++;
        pair_cooldown_end_[pair_id] = ros::Time::now() + ros::Duration(pair_cooldown_duration_);
    }

    // ----------------------------------------------------------------
    // Initial pose publication (once at startup)
    // ----------------------------------------------------------------

    void publishInitialPose(const ros::TimerEvent &)
    {
        if (initial_pose_published_)
            return;
        if (!initial_pose_x_converted_)
            return;

        geometry_msgs::PoseWithCovarianceStamped msg;
        msg.header.stamp = ros::Time::now();
        msg.header.frame_id = "map";
        msg.pose.pose.position.x = initial_pose_x_;
        msg.pose.pose.position.y = initial_pose_y_;
        msg.pose.pose.position.z = initial_pose_z_;
        if (initial_pose_yaw_ != 0.0)
        {
            tf2::Quaternion q;
            q.setRPY(0.0, 0.0, initial_pose_yaw_ * M_PI / 180.0);
            msg.pose.pose.orientation.x = q.x();
            msg.pose.pose.orientation.y = q.y();
            msg.pose.pose.orientation.z = q.z();
            msg.pose.pose.orientation.w = q.w();
        }
        else
        {
            msg.pose.pose.orientation.x = initial_pose_qx_;
            msg.pose.pose.orientation.y = initial_pose_qy_;
            msg.pose.pose.orientation.z = initial_pose_qz_;
            msg.pose.pose.orientation.w = initial_pose_qw_;
        }
        msg.pose.covariance = {
            0.25, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.25, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.06};

        initial_pose_pub_.publish(msg);
        initial_pose_published_ = true;
        initial_pose_pub_time_ = ros::Time::now();
        ROS_INFO_STREAM("costmap_jumper: published initial pose ["
                        << initial_pose_x_ << ", " << initial_pose_y_ << "]");
    }

    // ----------------------------------------------------------------
    // Region helpers
    // ----------------------------------------------------------------

    char regionOfPoint(double wx, double wy) const
    {
        if (transition_pairs_.empty())
            return '\0';
        double min_dist[26];
        std::fill(min_dist, min_dist + 26, std::numeric_limits<double>::max());
        for (const auto &p : transition_pairs_)
        {
            int idxA = p.pair_id;
            int idxB = p.pair_id + 1;
            double dA = std::hypot(wx - p.awx, wy - p.awy);
            double dB = std::hypot(wx - p.bwx, wy - p.bwy);
            if (dA < min_dist[idxA]) min_dist[idxA] = dA;
            if (dB < min_dist[idxB]) min_dist[idxB] = dB;
        }
        int best = 0;
        for (int i = 1; i < 26; ++i)
            if (min_dist[i] < min_dist[best]) best = i;
        return 'A' + best;
    }

    // ----------------------------------------------------------------
    // Region publication
    // ----------------------------------------------------------------

    void publishRegion()
    {
        std_msgs::Char msg;
        msg.data = current_region_;
        region_pub_.publish(msg);
        ROS_INFO_STREAM("costmap_jumper: region = " << current_region_);
    }

    void publishCentroids()
    {
        std_msgs::Float64MultiArray msg;
        for (const auto &pair : transition_pairs_)
        {
            if (!pair.traced)
                continue;
            msg.data.push_back(pair.pair_id);
            msg.data.push_back(pair.cx_A);
            msg.data.push_back(pair.cy_A);
            msg.data.push_back(pair.cx_B);
            msg.data.push_back(pair.cy_B);
        }
        centroid_pub_.publish(msg);
    }

    // ----------------------------------------------------------------
    // Helpers
    // ----------------------------------------------------------------

    int yamlToCellI(int pixel_x) const
    {
        double mx = yaml_origin_x_ + static_cast<double>(pixel_x) * yaml_resolution_;
        unsigned int ix, iy;
        if (cm_.worldToMap(mx, 0.0, ix, iy))
            return static_cast<int>(ix);
        return static_cast<int>(std::floor((mx - cm_.getOriginX()) / cm_.getResolution()));
    }

    int yamlToCellJ(int pixel_y) const
    {
        unsigned int sy = cm_.getSizeInCellsY();
        if (sy == 0)
            sy = 512;
        return static_cast<int>(sy) - 1 - pixel_y;
    }

    // ----------------------------------------------------------------
    // Members
    // ----------------------------------------------------------------

    ros::NodeHandle nh_;
    ros::NodeHandle private_nh_;
    tf2_ros::Buffer tf_buffer_;
    tf2_ros::TransformListener tf_listener_;
    ros::Publisher initial_pose_pub_;
    ros::Publisher transition_jumped_pub_;
    ros::Publisher transition_marker_pub_;
    ros::Publisher region_pub_;
    ros::Publisher centroid_pub_;
    ros::Subscriber costmap_sub_;
    std::string costmap_topic_;
    ros::Timer publish_initial_pose_timer_;
    ros::Timer check_timer_;

    // Transition pairs
    std::vector<TransitionPair> transition_pairs_;

    // Per-region override orientations (loaded from YAML)
    std::map<char, geometry_msgs::Quaternion> region_orientations_;

    // YAML metadata
    double yaml_resolution_{0.01};
    double yaml_origin_x_{-2.56};
    double yaml_origin_y_{-2.56};

    // Costmap data (from /move_base_node/global_costmap/costmap)
    bool cm_received_{false};
    bool traced_{false};
    ros::Time transition_last_diag_;
    costmap_2d::Costmap2D cm_;

    // Initial pose (for startup)
    bool initial_pose_published_{false};
    bool initial_pose_x_converted_{false};
    ros::Time initial_pose_pub_time_;
    double initial_pose_pixel_x_{0.0};
    double initial_pose_pixel_y_{0.0};
    double initial_pose_x_{0.0};
    double initial_pose_y_{0.0};
    double initial_pose_z_{0.0};
    double initial_pose_yaw_{0.0};
    double initial_pose_qx_{0.0};
    double initial_pose_qy_{0.0};
    double initial_pose_qz_{0.0};
    double initial_pose_qw_{1.0};

    // Jump state
    ros::Time last_jump_stamp_;
    double jump_cooldown_{2.0};
    int jump_count_{0};

    // TF / check params
    std::string base_frame_{"base_link"};
    double check_rate_{20.0};
    ros::Time startup_time_;
    double initial_jump_delay_{5.0};

    // Per-pair cooldown to prevent back-and-forth
    double pair_cooldown_duration_{5.0};
    std::map<int, ros::Time> pair_cooldown_end_;

    // Current region tracking
    char current_region_{'\0'};

    // ICP toggle
    ros::Publisher toggle_icp_pub_;
    ros::Publisher transition_vel_pub_;

    // Expansion wait
    ros::Subscriber cmd_vel_sub_;
    geometry_msgs::Twist last_cmd_vel_;
    bool waiting_for_jump_{false};
    ros::Time wait_start_time_;
    int pending_pair_id_{-1};
    bool pending_side_a_{true};
    ros::Time last_countdown_log_;
    double expansion_radius_{0.45};
    double jump_wait_duration_{0.0};
    bool enable_waiting_{true};
    double jump_pose_duration_{1.0};

    // Pitch-based jump detection
    ros::Subscriber imu_sub_;
    double pitch_current_{0.0};
    double pitch_baseline_{0.0};
    double pitch_threshold_{12.0};
    bool pitch_jump_enabled_{true};
};

int main(int argc, char **argv)
{
    ros::init(argc, argv, "costmap_jumper");
    CostmapJumperNode node;
    ros::spin();
    return 0;
}
