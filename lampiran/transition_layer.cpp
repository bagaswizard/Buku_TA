#include <costmap_2d/transition_layer.h>
#include <costmap_2d/costmap_math.h>
#include <pluginlib/class_list_macros.hpp>
#include <tf2/convert.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.h>
#include <queue>

PLUGINLIB_EXPORT_CLASS(costmap_2d::TransitionLayer, costmap_2d::Layer)

using costmap_2d::FREE_SPACE;
using costmap_2d::LETHAL_OBSTACLE;
using costmap_2d::NO_INFORMATION;

namespace costmap_2d
{

    TransitionLayer::TransitionLayer()
        : dsrv_(NULL),
          map_received_(false),
          has_updated_data_(false),
          lethal_threshold_(100),
          unknown_cost_value_(NO_INFORMATION),
          transition_expansion_(0.0)
    {
    }

    TransitionLayer::~TransitionLayer()
    {
        if (dsrv_)
            delete dsrv_;
    }

    void TransitionLayer::onInitialize()
    {
        ros::NodeHandle nh("~/" + name_), g_nh;
        current_ = true;

        global_frame_ = layered_costmap_->getGlobalFrameID();

        nh.param("map_topic", map_topic_, std::string("transition_map"));
        nh.param("track_unknown_space", track_unknown_space_, true);
        nh.param("use_maximum", use_maximum_, true);
        nh.param("transition_expansion", transition_expansion_, 0.0);

        int temp_lethal_threshold, temp_unknown_cost_value;
        nh.param("lethal_cost_threshold", temp_lethal_threshold, int(100));
        nh.param("unknown_cost_value", temp_unknown_cost_value, int(-1));

        lethal_threshold_ = std::max(std::min(temp_lethal_threshold, 100), 0);
        unknown_cost_value_ = temp_unknown_cost_value;

        ROS_INFO("TransitionLayer: Subscribing to topic '%s' with expansion radius %.2f m",
                 map_topic_.c_str(), transition_expansion_);

        if (map_sub_.getTopic() != ros::names::resolve(map_topic_))
        {
            map_sub_ = g_nh.subscribe(map_topic_, 1, &TransitionLayer::incomingMap, this);
            map_received_ = false;
            has_updated_data_ = false;

            ros::Rate r(10);
            int max_wait_cycles = 50; // 5 seconds at 10 Hz
            int wait_cycles = 0;

            while (!map_received_ && g_nh.ok() && wait_cycles < max_wait_cycles)
            {
                ros::spinOnce();
                r.sleep();
                wait_cycles++;
            }

            if (!map_received_)
            {
                ROS_WARN("TransitionLayer: Timeout waiting for map on topic '%s'. Layer will be inactive until map arrives.",
                         map_topic_.c_str());
            }
            else
            {
                ROS_INFO("TransitionLayer: Received transition map %d X %d at %f m/pix",
                         getSizeInCellsX(), getSizeInCellsY(), getResolution());
            }
        }
        else
        {
            has_updated_data_ = true;
        }

        if (dsrv_)
        {
            delete dsrv_;
        }

        dsrv_ = new dynamic_reconfigure::Server<costmap_2d::GenericPluginConfig>(nh);
        dynamic_reconfigure::Server<costmap_2d::GenericPluginConfig>::CallbackType cb =
            [this](auto &config, auto level)
        { reconfigureCB(config, level); };
        dsrv_->setCallback(cb);

        nh.param("publish_grid", publish_grid_, false);
        if (publish_grid_)
        {
            grid_pub_ = nh.advertise<nav_msgs::OccupancyGrid>("grid", 1, true);
            ROS_INFO("TransitionLayer: publishing individual grid on ~/%s/grid", name_.c_str());
        }
    }

    void TransitionLayer::reconfigureCB(costmap_2d::GenericPluginConfig &config, uint32_t level)
    {
        if (config.enabled != enabled_)
        {
            enabled_ = config.enabled;
            has_updated_data_ = true;
            x_ = y_ = 0;
            width_ = size_x_;
            height_ = size_y_;
        }
    }

    void TransitionLayer::matchSize()
    {
        if (!layered_costmap_->isRolling())
        {
            Costmap2D *master = layered_costmap_->getCostmap();
            resizeMap(master->getSizeInCellsX(), master->getSizeInCellsY(), master->getResolution(),
                      master->getOriginX(), master->getOriginY());
        }
    }

    void TransitionLayer::activate()
    {
        ROS_DEBUG("TransitionLayer: Activating");
    }

    void TransitionLayer::deactivate()
    {
        ROS_DEBUG("TransitionLayer: Deactivating");
    }

    void TransitionLayer::reset()
    {
        ROS_DEBUG("TransitionLayer: Resetting");
        resetMap(0, 0, getSizeInCellsX(), getSizeInCellsY());
    }

    unsigned char TransitionLayer::interpretValue(unsigned char value)
    {
        if (value == 255)
        {
            // 255 pixels map to TRANSITION_MAIN_DATA (252)
            return TRANSITION_MAIN_DATA;
        }
        else if (track_unknown_space_ && value == unknown_cost_value_)
        {
            return NO_INFORMATION;
        }
        else if (!track_unknown_space_ && value == unknown_cost_value_)
        {
            return FREE_SPACE;
        }
        else if (value == 0)
        {
            return FREE_SPACE;
        }
        else if (value >= lethal_threshold_)
        {
            return TRANSITION_LETHAL; // Use 250 (same as inflation layer lethal)
        }

        // Scale intermediate values between 1 and TRANSITION_MAX_INTERMEDIATE
        double scale = (double)value / lethal_threshold_;
        return std::max(1, std::min((int)TRANSITION_MAX_INTERMEDIATE, (int)(scale * (TRANSITION_LETHAL))));
    }

    void TransitionLayer::incomingMap(const nav_msgs::OccupancyGridConstPtr &new_map)
    {
        unsigned int size_x = new_map->info.width, size_y = new_map->info.height;

        ROS_DEBUG("TransitionLayer: Received map %d X %d at %f m/pix",
                  size_x, size_y, new_map->info.resolution);

        Costmap2D *master = layered_costmap_->getCostmap();
        if (!layered_costmap_->isRolling() &&
            (master->getSizeInCellsX() != size_x ||
             master->getSizeInCellsY() != size_y ||
             master->getResolution() != new_map->info.resolution ||
             master->getOriginX() != new_map->info.origin.position.x ||
             master->getOriginY() != new_map->info.origin.position.y))
        {
            ROS_INFO("TransitionLayer: Resizing costmap to %d X %d at %f m/pix",
                     size_x, size_y, new_map->info.resolution);
            layered_costmap_->resizeMap(size_x, size_y, new_map->info.resolution,
                                        new_map->info.origin.position.x,
                                        new_map->info.origin.position.y,
                                        true);
        }
        else if (size_x_ != size_x || size_y_ != size_y ||
                 resolution_ != new_map->info.resolution ||
                 origin_x_ != new_map->info.origin.position.x ||
                 origin_y_ != new_map->info.origin.position.y)
        {
            ROS_INFO("TransitionLayer: Resizing layer to %d X %d at %f m/pix",
                     size_x, size_y, new_map->info.resolution);
            resizeMap(size_x, size_y, new_map->info.resolution,
                      new_map->info.origin.position.x, new_map->info.origin.position.y);
        }

        unsigned int index = 0;
        for (unsigned int j = 0; j < size_y; j++)
        {
            for (unsigned int i = 0; i < size_x; i++)
            {
                unsigned char value = new_map->data[index];
                setCost(i, j, interpretValue(value));
                index++;
            }
        }

        map_received_ = true;
        has_updated_data_ = true;
        x_ = y_ = 0;
        width_ = size_x_;
        height_ = size_y_;

        ROS_INFO("TransitionLayer: Map data loaded. Size: %u x %u, Resolution: %f",
                 size_x_, size_y_, resolution_);
    }

    void TransitionLayer::applyTransitionExpansion()
    {
        // Expansion is now handled by TransitionExpansionLayer - this method is kept for compatibility
        ROS_DEBUG("TransitionLayer: Expansion is now handled by TransitionExpansionLayer");
    }

    void TransitionLayer::updateBounds(double robot_x, double robot_y, double robot_yaw,
                                       double *min_x, double *min_y, double *max_x, double *max_y)
    {
        if (!enabled_ || !map_received_)
            return;

        // Always update bounds to cover the entire layer area when map is available
        *min_x = std::min(*min_x, origin_x_);
        *min_y = std::min(*min_y, origin_y_);
        *max_x = std::max(*max_x, origin_x_ + size_x_ * resolution_);
        *max_y = std::max(*max_y, origin_y_ + size_y_ * resolution_);

        // Only clear updated flag if we had a targeted update
        if (has_updated_data_)
        {
            has_updated_data_ = false;
        }
    }

    void TransitionLayer::updateCosts(Costmap2D &master_grid, int min_i, int min_j, int max_i, int max_j)
    {
        if (!enabled_)
        {
            ROS_DEBUG("TransitionLayer::updateCosts: Layer disabled");
            return;
        }

        if (!map_received_)
        {
            ROS_DEBUG("TransitionLayer::updateCosts: Map not received yet");
            return;
        }

        unsigned char *master_array = master_grid.getCharMap();
        unsigned char *local_array = getCharMap();

        // Process the ENTIRE layer since transition data is static
        unsigned int main_count = 0;
        unsigned int total_count = 0;

        for (unsigned int j = 0; j < size_y_; j++)
        {
            for (unsigned int i = 0; i < size_x_; i++)
            {
                unsigned int index = getIndex(i, j);
                unsigned int master_index = master_grid.getIndex(i, j);

                unsigned char cost = local_array[index];

                // Copy all transition layer costs, not just main data
                if (cost > 0) // Skip free space / unknown
                {
                    total_count++;
                    if (cost == TRANSITION_MAIN_DATA)
                        main_count++;

                    unsigned char old_cost = master_array[master_index];
                    if (use_maximum_)
                    {
                        master_array[master_index] = std::max(old_cost, cost);
                    }
                    else
                    {
                        master_array[master_index] = cost;
                    }
                }
            }
        }

        static bool logged = false;
        if (!logged)
        {
            ROS_INFO("TransitionLayer::updateCosts: enabled_=%d, map_received_=%d, copied %u cells (%u TRANSITION_MAIN_DATA), size_x_=%u, size_y_=%u, use_maximum_=%d",
                     enabled_, map_received_, total_count, main_count, size_x_, size_y_, use_maximum_);
            logged = true;
        }

        if (publish_grid_)
        {
            publishGrid();
        }
    }

    void TransitionLayer::publishGrid()
    {
        costmap_2d::Costmap2D *master = layered_costmap_->getCostmap();
        unsigned int size = master->getSizeInCellsX() * master->getSizeInCellsY();
        nav_msgs::OccupancyGrid msg;
        msg.header.frame_id = global_frame_;
        msg.header.stamp = ros::Time::now();
        msg.info.resolution = master->getResolution();
        msg.info.width = master->getSizeInCellsX();
        msg.info.height = master->getSizeInCellsY();
        msg.info.origin.position.x = master->getOriginX();
        msg.info.origin.position.y = master->getOriginY();
        msg.info.origin.orientation.w = 1.0;

        msg.data.resize(size);
        unsigned char *master_data = master->getCharMap();
        for (unsigned int i = 0; i < size; i++)
        {
            unsigned char c = master_data[i];
            if (c == NO_INFORMATION)
                msg.data[i] = -1;
            else if (c == TRANSITION_MAIN_DATA || c == TRANSITION_LETHAL)
                msg.data[i] = 100;
            else
                msg.data[i] = 0;
        }
        grid_pub_.publish(msg);
    }

} // namespace costmap_2d
