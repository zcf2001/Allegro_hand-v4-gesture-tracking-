import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/fzc/allegro_hand_linux_v4/ros2_source/src/install/mediapipe_test'
