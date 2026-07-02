#include <ros/ros.h>
#include <actionlib/client/simple_action_client.h>
#include <move_base_msgs/MoveBaseAction.h>
#include <geometry_msgs/PoseStamped.h>
#include <std_msgs/Char.h>
#include <std_msgs/Empty.h>
#include <std_msgs/Float64MultiArray.h>
#include <visualization_msgs/MarkerArray.h>
#include <visualization_msgs/Marker.h>
#include <tf2_ros/transform_listener.h>
#include <yaml-cpp/yaml.h>
#include <string>
#include <vector>
#include <cmath>
#include <limits>
#include <algorithm>

struct TransitionSeed
{
    int pair_id;
    int ax, ay;
    int bx, by;
    double awx, awy;
    double bwx, bwy;
};

struct InterceptStep
{
    int pair_id;
    bool enter_from_A;
    double ix, iy;
};

class PathInterceptor
{
public:
    PathInterceptor()
        : ac_("move_base", true)
        , tf_buffer_()
        , tf_listener_(tf_buffer_)
        , state_(IDLE)
        , robot_region_(0)
        , jumped_(false)
        , retries_(0)
        , current_step_(0)
    {
        ros::NodeHandle nh, pnh("~");

        std::string yaml_path;
        pnh.param("transition_pairs_yaml", yaml_path, std::string(""));
        if (!yaml_path.empty())
            loadYaml(yaml_path);

        goal_sub_ = nh.subscribe("/move_base_simple/goal", 1, &PathInterceptor::goalCallback, this);
        jumped_sub_ = nh.subscribe("/transition_jumped", 1, &PathInterceptor::jumpedCallback, this);
        centroid_sub_ = nh.subscribe("/transition_centroids", 1, &PathInterceptor::centroidCallback, this);
        timer_ = nh.createTimer(ros::Duration(0.5), &PathInterceptor::regionTimerCallback, this);

        marker_pub_ = nh.advertise<visualization_msgs::MarkerArray>("/path_interceptor/markers", 1, true);

        ROS_INFO("path_interceptor: waiting for move_base action server...");
        ac_.waitForServer();
        ROS_INFO("path_interceptor: started with %zu pairs", seeds_.size());
    }

private:
    enum State { IDLE, INTERCEPT, FINAL_LEG, DIRECT };
    static const int MAX_RETRIES = 1;

    State state_;
    char robot_region_;
    geometry_msgs::PoseStamped final_goal_;
    bool jumped_;
    int retries_;

    std::vector<TransitionSeed> seeds_;
    std::vector<InterceptStep> pending_steps_;
    int current_step_;

    double yaml_resolution_{0.01};
    double yaml_origin_x_{-2.56};
    double yaml_origin_y_{-2.56};

    actionlib::SimpleActionClient<move_base_msgs::MoveBaseAction> ac_;
    tf2_ros::Buffer tf_buffer_;
    tf2_ros::TransformListener tf_listener_;
    ros::Subscriber goal_sub_, jumped_sub_, centroid_sub_;
    ros::Timer timer_;
    ros::Publisher marker_pub_;

    std::map<int, geometry_msgs::Point> centroid_A_;
    std::map<int, geometry_msgs::Point> centroid_B_;

    // ------------------------------------------------------------------
    // YAML loading
    // ------------------------------------------------------------------

    bool loadYaml(const std::string &path)
    {
        YAML::Node doc;
        try
        {
            doc = YAML::LoadFile(path);
        }
        catch (...)
        {
            ROS_FATAL("path_interceptor: failed to load %s", path.c_str());
            return false;
        }

        if (doc["resolution"]) yaml_resolution_ = doc["resolution"].as<double>();
        if (doc["origin"] && doc["origin"].IsSequence() && doc["origin"].size() >= 2)
        {
            yaml_origin_x_ = doc["origin"][0].as<double>();
            yaml_origin_y_ = doc["origin"][1].as<double>();
        }

        const YAML::Node &transitions = doc["transitions"];
        if (!transitions || !transitions.IsSequence())
        {
            ROS_WARN("path_interceptor: no transitions array");
            return true;
        }

        for (std::size_t i = 0; i < transitions.size(); ++i)
        {
            const YAML::Node &t = transitions[i];
            if (!t["first_pixel_A"] || !t["first_pixel_B"])
                continue;

            TransitionSeed s;
            s.pair_id = t["pair"] ? t["pair"].as<int>() : static_cast<int>(i);
            s.ax = t["first_pixel_A"][0].as<int>();
            s.ay = t["first_pixel_A"][1].as<int>();
            s.bx = t["first_pixel_B"][0].as<int>();
            s.by = t["first_pixel_B"][1].as<int>();

            s.awx = yaml_origin_x_ + s.ax * yaml_resolution_;
            s.awy = -(yaml_origin_y_ + s.ay * yaml_resolution_);
            s.bwx = yaml_origin_x_ + s.bx * yaml_resolution_;
            s.bwy = -(yaml_origin_y_ + s.by * yaml_resolution_);

            seeds_.push_back(s);
            ROS_INFO("path_interceptor: pair %d  A(%.2f,%.2f)  B(%.2f,%.2f)",
                     s.pair_id, s.awx, s.awy, s.bwx, s.bwy);
        }
        return true;
    }

    // ------------------------------------------------------------------
    // Region helpers
    // ------------------------------------------------------------------
    // Pair i connects region 'A'+i  <->  'A'+i+1.
    // seed_A lives in region 'A'+i, seed_B lives in region 'A'+i+1.

    const TransitionSeed *findSeed(int pair_id) const
    {
        for (const auto &s : seeds_)
            if (s.pair_id == pair_id)
                return &s;
        return nullptr;
    }

    char regionOfPoint(double wx, double wy) const
    {
        double min_dist[26];
        std::fill(min_dist, min_dist + 26, std::numeric_limits<double>::max());

        for (const auto &s : seeds_)
        {
            int idxA = s.pair_id;
            int idxB = s.pair_id + 1;
            double dA = std::hypot(wx - s.awx, wy - s.awy);
            double dB = std::hypot(wx - s.bwx, wy - s.bwy);
            if (dA < min_dist[idxA]) min_dist[idxA] = dA;
            if (dB < min_dist[idxB]) min_dist[idxB] = dB;
        }

        int best = 0;
        for (int i = 1; i < 26; ++i)
            if (min_dist[i] < min_dist[best]) best = i;
        return 'A' + best;
    }

    // Build an ordered list of steps to go from `from` to `to`
    // Each step crosses one pair. Direction determines enter_from_A.
    void buildPath(char from, char to, std::vector<InterceptStep> &out) const
    {
        out.clear();
        int fi = from - 'A';
        int ti = to - 'A';

        if (fi < ti)
        {
            for (int i = fi; i < ti; ++i)
            {
                InterceptStep step;
                step.pair_id = i;
                step.enter_from_A = true;
                auto it = centroid_A_.find(i);
                if (it != centroid_A_.end())
                {
                    step.ix = it->second.x;
                    step.iy = it->second.y;
                }
                else
                {
                    const TransitionSeed *s = findSeed(i);
                    if (!s) continue;
                    step.ix = s->awx;
                    step.iy = s->awy;
                }
                out.push_back(step);
            }
        }
        else
        {
            for (int i = fi - 1; i >= ti; --i)
            {
                InterceptStep step;
                step.pair_id = i;
                step.enter_from_A = false;
                auto it = centroid_B_.find(i);
                if (it != centroid_B_.end())
                {
                    step.ix = it->second.x;
                    step.iy = it->second.y;
                }
                else
                {
                    const TransitionSeed *s = findSeed(i);
                    if (!s) continue;
                    step.ix = s->bwx;
                    step.iy = s->bwy;
                }
                out.push_back(step);
            }
        }
    }

    // ------------------------------------------------------------------
    // Centroid callback
    // ------------------------------------------------------------------

    void centroidCallback(const std_msgs::Float64MultiArray::ConstPtr &msg)
    {
        const auto &d = msg->data;
        for (std::size_t i = 0; i + 4 < d.size(); i += 5)
        {
            int pid = static_cast<int>(d[i]);
            geometry_msgs::Point ca, cb;
            ca.x = d[i + 1]; ca.y = d[i + 2];
            cb.x = d[i + 3]; cb.y = d[i + 4];
            centroid_A_[pid] = ca;
            centroid_B_[pid] = cb;
            ROS_DEBUG("path_interceptor: centroid pair %d  A(%.2f,%.2f)  B(%.2f,%.2f)",
                      pid, ca.x, ca.y, cb.x, cb.y);
        }
    }

    // ------------------------------------------------------------------
    // Current robot orientation (ignore goal orientation)
    // ------------------------------------------------------------------

    geometry_msgs::Quaternion currentRobotOrientation() const
    {
        try
        {
            auto tf = tf_buffer_.lookupTransform("map", "base_link", ros::Time(0));
            return tf.transform.rotation;
        }
        catch (tf2::TransformException &)
        {
            geometry_msgs::Quaternion q;
            q.w = 1.0;
            return q;
        }
    }

    // ------------------------------------------------------------------
    // Callbacks
    // ------------------------------------------------------------------

    void regionTimerCallback(const ros::TimerEvent &)
    {
        try
        {
            auto tf = tf_buffer_.lookupTransform("map", "base_link", ros::Time(0));
            robot_region_ = regionOfPoint(tf.transform.translation.x, tf.transform.translation.y);
        }
        catch (tf2::TransformException &)
        {
            robot_region_ = 0;
        }
    }

    void jumpedCallback(const std_msgs::Empty::ConstPtr &)
    {
        if (state_ != INTERCEPT) return;

        ROS_INFO("path_interceptor: transition jumped");
        jumped_ = true;
        retries_ = 0;
        ac_.cancelAllGoals();
        ros::Duration(0.05).sleep();
        advanceIntercept();
    }

    void goalCallback(const geometry_msgs::PoseStamped::ConstPtr &msg)
    {
        if (state_ != IDLE)
        {
            ROS_WARN("path_interceptor: aborting current goal");
            ac_.cancelAllGoals();
            ros::Duration(0.1).sleep();
            clearFuturePath();
            state_ = IDLE;
        }

        if (robot_region_ == 0)
        {
            ROS_WARN("path_interceptor: region unknown -- forwarding directly");
            forwardDirect(*msg);
            return;
        }

        char goal_region = regionOfPoint(msg->pose.position.x, msg->pose.position.y);
        ROS_INFO("path_interceptor: robot in %c, goal in %c", robot_region_, goal_region);

        if (robot_region_ == goal_region)
        {
            forwardDirect(*msg);
            return;
        }

        // Build multi-step path through the region chain
        final_goal_ = *msg;
        buildPath(robot_region_, goal_region, pending_steps_);

        if (pending_steps_.empty())
        {
            ROS_WARN("path_interceptor: empty path -- forwarding directly");
            forwardDirect(*msg);
            return;
        }

        ROS_INFO("path_interceptor: path requires %zu transition(s)", pending_steps_.size());
        for (size_t i = 0; i < pending_steps_.size(); ++i)
            ROS_INFO("  step %zu: pair %d  %s  goal (%.2f, %.2f)",
                     i, pending_steps_[i].pair_id,
                     pending_steps_[i].enter_from_A ? "A->B" : "B->A",
                     pending_steps_[i].ix, pending_steps_[i].iy);

        current_step_ = 0;
        jumped_ = false;
        retries_ = 0;
        sendInterceptGoal(current_step_);
        state_ = INTERCEPT;
    }

    void doneCallback(const actionlib::SimpleClientGoalState &state,
                      const move_base_msgs::MoveBaseResult::ConstPtr &)
    {
        if (state_ == INTERCEPT)
        {
            if (jumped_) return;
            return;
        }
        else if (state_ == FINAL_LEG)
        {
            if (state == actionlib::SimpleClientGoalState::SUCCEEDED)
            {
                ROS_INFO("path_interceptor: goal SUCCEEDED");
                state_ = IDLE;
                clearFuturePath();
            }
            else if (retries_ < MAX_RETRIES)
            {
                ROS_WARN("path_interceptor: goal %s -- retrying once", state.toString().c_str());
                retries_++;
                sendFinalGoal();
            }
            else
            {
                ROS_ERROR("path_interceptor: goal failed after retry -- giving up");
                state_ = IDLE;
                clearFuturePath();
            }
        }
        else if (state_ == DIRECT)
        {
            ROS_INFO("path_interceptor: direct goal %s", state.toString().c_str());
            state_ = IDLE;
        }
    }

    // ------------------------------------------------------------------
    // State machine helpers
    // ------------------------------------------------------------------

    void advanceIntercept()
    {
        current_step_++;
        if (current_step_ < static_cast<int>(pending_steps_.size()))
        {
            jumped_ = false;
            sendInterceptGoal(current_step_);
        }
        else
        {
            ROS_INFO("path_interceptor: all transitions done -- sending final goal");
            sendFinalGoal();
            state_ = FINAL_LEG;
        }
    }

    void sendInterceptGoal(int step_idx)
    {
        const InterceptStep &step = pending_steps_[step_idx];

        move_base_msgs::MoveBaseGoal goal;
        goal.target_pose.header.frame_id = "map";
        goal.target_pose.header.stamp = ros::Time::now();
        goal.target_pose.pose.position.x = step.ix;
        goal.target_pose.pose.position.y = step.iy;
        goal.target_pose.pose.orientation = currentRobotOrientation();

        ROS_INFO("path_interceptor: step %d/%zu  pair %d  goal (%.2f, %.2f)",
                 step_idx + 1, pending_steps_.size(), step.pair_id, step.ix, step.iy);
        publishFutureSteps(step_idx);

        ac_.sendGoal(goal, boost::bind(&PathInterceptor::doneCallback, this, _1, _2));
    }

    geometry_msgs::Point destPointForStep(const InterceptStep &s) const
    {
        geometry_msgs::Point p;
        if (s.enter_from_A)
        {
            auto it = centroid_B_.find(s.pair_id);
            if (it != centroid_B_.end()) p = it->second;
            else { const TransitionSeed *seed = findSeed(s.pair_id); p.x = seed->bwx; p.y = seed->bwy; }
        }
        else
        {
            auto it = centroid_A_.find(s.pair_id);
            if (it != centroid_A_.end()) p = it->second;
            else { const TransitionSeed *seed = findSeed(s.pair_id); p.x = seed->awx; p.y = seed->awy; }
        }
        return p;
    }

    void publishFutureSteps(int step_idx)
    {
        clearFuturePath();
        visualization_msgs::MarkerArray arr;
        double fx = final_goal_.pose.position.x;
        double fy = final_goal_.pose.position.y;

        for (int i = step_idx; i < static_cast<int>(pending_steps_.size()); ++i)
        {
            geometry_msgs::Point from = destPointForStep(pending_steps_[i]);
            geometry_msgs::Point to;
            if (i + 1 < static_cast<int>(pending_steps_.size()))
                { to.x = pending_steps_[i + 1].ix; to.y = pending_steps_[i + 1].iy; }
            else
                { to.x = fx; to.y = fy; }

            visualization_msgs::Marker m;
            m.header.frame_id = "map";
            m.header.stamp = ros::Time::now();
            m.ns = "future_path";
            m.id = i;
            m.type = visualization_msgs::Marker::LINE_STRIP;
            m.action = visualization_msgs::Marker::ADD;
            m.scale.x = 0.02;
            m.color.a = 1.0;
            m.color.r = 0.0;
            m.color.g = 1.0;
            m.color.b = 1.0;
            m.pose.orientation.w = 1.0;
            geometry_msgs::Point p;
            p.z = 0;
            p.x = from.x; p.y = from.y; m.points.push_back(p);
            p.x = to.x;   p.y = to.y;   m.points.push_back(p);
            arr.markers.push_back(m);
        }
        marker_pub_.publish(arr);
    }

    void forwardDirect(const geometry_msgs::PoseStamped &pose)
    {
        clearFuturePath();
        move_base_msgs::MoveBaseGoal goal;
        goal.target_pose = pose;
        goal.target_pose.header.stamp = ros::Time::now();
        goal.target_pose.pose.orientation = currentRobotOrientation();

        ac_.sendGoal(goal, boost::bind(&PathInterceptor::doneCallback, this, _1, _2));
        state_ = DIRECT;
    }

    void sendFinalGoal()
    {
        clearFuturePath();
        move_base_msgs::MoveBaseGoal goal;
        goal.target_pose = final_goal_;
        goal.target_pose.header.stamp = ros::Time::now();
        goal.target_pose.pose.orientation = currentRobotOrientation();

        ac_.sendGoal(goal, boost::bind(&PathInterceptor::doneCallback, this, _1, _2));
    }

    // ------------------------------------------------------------------
    // Visualization
    // ------------------------------------------------------------------

    void clearFuturePath()
    {
        visualization_msgs::MarkerArray arr;
        visualization_msgs::Marker m;
        m.header.frame_id = "map";
        m.header.stamp = ros::Time::now();
        m.ns = "future_path";
        m.action = visualization_msgs::Marker::DELETEALL;
        arr.markers.push_back(m);
        marker_pub_.publish(arr);
    }
};

int main(int argc, char **argv)
{
    ros::init(argc, argv, "path_interceptor");
    PathInterceptor pi;
    ros::spin();
    return 0;
}
