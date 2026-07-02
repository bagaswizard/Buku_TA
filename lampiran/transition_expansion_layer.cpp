#include <costmap_2d/transition_expansion_layer.h>
#include <costmap_2d/costmap_math.h>
#include <pluginlib/class_list_macros.hpp>
#include <queue>

PLUGINLIB_EXPORT_CLASS(costmap_2d::TransitionExpansionLayer, costmap_2d::Layer)

using costmap_2d::LETHAL_OBSTACLE;
using costmap_2d::NO_INFORMATION;

namespace costmap_2d
{

    TransitionExpansionLayer::TransitionExpansionLayer()
        : expansion_radius_(0.0), cell_expansion_radius_(0), dsrv_(NULL), map_received_(false), map_updated_(false)
    {
        expansion_access_ = new boost::recursive_mutex();
    }

    TransitionExpansionLayer::~TransitionExpansionLayer()
    {
        if (dsrv_)
            delete dsrv_;
        if (expansion_access_)
            delete expansion_access_;
    }

    void TransitionExpansionLayer::onInitialize()
    {
        ros::NodeHandle nh("~/" + name_), g_nh;
        current_ = true;

        nh.param("expansion_radius", expansion_radius_, 0.0);
        nh.param("map_topic", map_topic_, std::string("transition_map"));

        ROS_INFO("TransitionExpansionLayer: Initialized with expansion_radius: %.2f m, map_topic: %s",
                 expansion_radius_, map_topic_.c_str());

        matchSize();

        if (map_sub_.getTopic() != ros::names::resolve(map_topic_))
        {
            map_sub_ = g_nh.subscribe(map_topic_, 1, &TransitionExpansionLayer::incomingMap, this);
            map_received_ = false;

            ros::Rate r(10);
            int max_wait_cycles = 50;
            int wait_cycles = 0;

            while (!map_received_ && g_nh.ok() && wait_cycles < max_wait_cycles)
            {
                ros::spinOnce();
                r.sleep();
                wait_cycles++;
            }

            if (!map_received_)
            {
                ROS_WARN("TransitionExpansionLayer: Timeout waiting for map on topic '%s'. Layer will be inactive.",
                         map_topic_.c_str());
            }
            else
            {
                ROS_INFO("TransitionExpansionLayer: Received map %d X %d at %f m/pix",
                         getSizeInCellsX(), getSizeInCellsY(), getResolution());
            }
        }
        else
        {
            map_received_ = true;
        }

        dynamic_reconfigure::Server<costmap_2d::GenericPluginConfig>::CallbackType cb =
            [this](auto &config, auto level)
        { reconfigureCB(config, level); };

        if (dsrv_ != NULL)
        {
            dsrv_->clearCallback();
            dsrv_->setCallback(cb);
        }
        else
        {
            dsrv_ = new dynamic_reconfigure::Server<costmap_2d::GenericPluginConfig>(
                ros::NodeHandle("~/" + name_));
            dsrv_->setCallback(cb);
        }

        nh.param("publish_grid", publish_grid_, false);
        if (publish_grid_)
        {
            grid_pub_ = nh.advertise<nav_msgs::OccupancyGrid>("grid", 1, true);
            ROS_INFO("TransitionExpansionLayer: publishing individual grid on ~/%s/grid", name_.c_str());
        }
    }

    void TransitionExpansionLayer::reconfigureCB(costmap_2d::GenericPluginConfig &config, uint32_t level)
    {
        enabled_ = config.enabled;
    }

    void TransitionExpansionLayer::matchSize()
    {
        if (!layered_costmap_->isRolling())
        {
            Costmap2D *master = layered_costmap_->getCostmap();
            resizeMap(master->getSizeInCellsX(), master->getSizeInCellsY(), master->getResolution(),
                      master->getOriginX(), master->getOriginY());
        }
    }

    void TransitionExpansionLayer::activate()
    {
        ROS_DEBUG("TransitionExpansionLayer: Activating");
    }

    void TransitionExpansionLayer::deactivate()
    {
        ROS_DEBUG("TransitionExpansionLayer: Deactivating");
    }

    void TransitionExpansionLayer::reset()
    {
        ROS_DEBUG("TransitionExpansionLayer: Resetting");
        resetMap(0, 0, getSizeInCellsX(), getSizeInCellsY());
        map_updated_ = false;
    }

    void TransitionExpansionLayer::updateBounds(double robot_x, double robot_y, double robot_yaw,
                                                double *min_x, double *min_y, double *max_x, double *max_y)
    {
        if (!enabled_)
            return;

        if (!map_received_)
            return;

        *min_x = std::min(*min_x, origin_x_);
        *min_y = std::min(*min_y, origin_y_);
        *max_x = std::max(*max_x, origin_x_ + size_x_ * resolution_);
        *max_y = std::max(*max_y, origin_y_ + size_y_ * resolution_);
    }

    void TransitionExpansionLayer::incomingMap(const nav_msgs::OccupancyGridConstPtr &new_map)
    {
        unsigned int size_x = new_map->info.width, size_y = new_map->info.height;

        Costmap2D *master = layered_costmap_->getCostmap();
        if (!layered_costmap_->isRolling() &&
            (master->getSizeInCellsX() != size_x ||
             master->getSizeInCellsY() != size_y ||
             master->getResolution() != new_map->info.resolution ||
             master->getOriginX() != new_map->info.origin.position.x ||
             master->getOriginY() != new_map->info.origin.position.y))
        {
            ROS_INFO("TransitionExpansionLayer: Resizing costmap to %d X %d at %f m/pix",
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
            ROS_INFO("TransitionExpansionLayer: Resizing layer to %d X %d at %f m/pix",
                     size_x, size_y, new_map->info.resolution);
            resizeMap(size_x, size_y, new_map->info.resolution,
                      new_map->info.origin.position.x, new_map->info.origin.position.y);
        }

        pending_map_ = *new_map;
        map_received_ = true;
        map_updated_ = true;
    }

    void TransitionExpansionLayer::updateCosts(Costmap2D &master_grid, int min_i, int min_j, int max_i, int max_j)
    {
        if (!enabled_)
            return;

        if (!map_received_)
            return;

        boost::unique_lock<boost::recursive_mutex> lock(*expansion_access_);

        bool was_updated = map_updated_;

        if (map_updated_)
        {
            map_updated_ = false;

            resetMap(0, 0, getSizeInCellsX(), getSizeInCellsY());

            unsigned int size_x = getSizeInCellsX(), size_y = getSizeInCellsY();

            std::vector<std::pair<int, int>> seed_cells;
            for (unsigned int j = 0; j < size_y; j++)
            {
                for (unsigned int i = 0; i < size_x; i++)
                {
                    if (pending_map_.data[j * size_x + i] > 0)
                    {
                        seed_cells.push_back(std::make_pair(i, j));
                    }
                }
            }

            if (seed_cells.empty())
            {
                ROS_WARN("TransitionExpansionLayer: No occupied cells found in map, nothing to expand");
                return;
            }

            cell_expansion_radius_ = (unsigned int)ceil(expansion_radius_ / resolution_);

            std::queue<std::pair<int, int>> q;
            std::map<int, int> distance_map;

            for (auto &cell : seed_cells)
            {
                q.push(cell);
                distance_map[getIndex(cell.first, cell.second)] = 0;
            }

            unsigned int expansion_count = 0;
            while (!q.empty())
            {
                int x = q.front().first, y = q.front().second;
                q.pop();

                int current_index = getIndex(x, y);
                int current_distance = distance_map[current_index];

                if (current_distance >= (int)cell_expansion_radius_)
                    continue;

                int dx[] = {-1, 1, 0, 0};
                int dy[] = {0, 0, -1, 1};

                for (int dir = 0; dir < 4; dir++)
                {
                    int nx = x + dx[dir], ny = y + dy[dir];

                    if (nx >= 0 && nx < (int)size_x && ny >= 0 && ny < (int)size_y)
                    {
                        if (master_grid.getCost(nx, ny) == costmap_2d::LETHAL_OBSTACLE)
                            continue;

                        int neighbor_index = getIndex(nx, ny);
                        int new_distance = current_distance + 1;

                        if (distance_map.find(neighbor_index) == distance_map.end() &&
                            new_distance <= (int)cell_expansion_radius_)
                        {
                            distance_map[neighbor_index] = new_distance;

                            if (pending_map_.data[ny * size_x + nx] <= 0)
                            {
                                setCost(nx, ny, TRANSITION_EXPANSION);
                                expansion_count++;
                            }

                            q.push(std::make_pair(nx, ny));
                        }
                    }
                }
            }

            ROS_INFO("TransitionExpansionLayer: Map processed - expanded %u cells from %zu seed cells (radius: %u cells, %.2f m)",
                     expansion_count, seed_cells.size(), cell_expansion_radius_, expansion_radius_);
        }

        // Copy expansion into master, but only on definitely-free cells
        for (int j = min_j; j <= max_j; j++)
        {
            for (int i = min_i; i <= max_i; i++)
            {
                int idx = getIndex(i, j);
                unsigned char local = costmap_[idx];
                if (local == NO_INFORMATION)
                    continue;

                unsigned char master = master_grid.getCost(i, j);
                if (master == costmap_2d::LETHAL_OBSTACLE ||
                    master == costmap_2d::NO_INFORMATION)
                    continue;

                if (local == TRANSITION_EXPANSION)
                    master_grid.setCost(i, j, local);
            }
        }

        if (publish_grid_ && was_updated)
        {
            publishGrid();
        }
    }

    void TransitionExpansionLayer::publishGrid()
    {
        costmap_2d::Costmap2D *master = layered_costmap_->getCostmap();
        unsigned int size = master->getSizeInCellsX() * master->getSizeInCellsY();
        nav_msgs::OccupancyGrid msg;
        msg.header.frame_id = layered_costmap_->getGlobalFrameID();
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
            else if (c == TRANSITION_EXPANSION)
                msg.data[i] = 90;
            else
                msg.data[i] = 0;
        }
        grid_pub_.publish(msg);
    }

} // namespace costmap_2d
