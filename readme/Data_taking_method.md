-ICP data vs real location data with various transition radius
-ICP data vs real data in rough terrain
-Path planning vs ground truth with various costmap inflation values
-path planning local in various unknown obstacles added

analyse path results in various costmap values

rostopic pub -1 /move_base_simple/goal geometry_msgs/PoseStamped \
'{header: {frame_id: map}, pose: {position: {x: -2.1, y: 1.7, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: -0.033, w: 1.0}}}'