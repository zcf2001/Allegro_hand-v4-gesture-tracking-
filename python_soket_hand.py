import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState  # ⚠️ 请根据官方驱动实际接收的类型修改
import cv2
import mediapipe as mp
import numpy as np

class MediaPipeAllegroBridge(Node):
    def __init__(self):
        super().__init__('mediapipe_allegro_bridge')
        
        # 创建发布者：发布角度数据给灵巧手驱动
        # ⚠️ '/allegro_hand/joint_cmd' 需要替换为官方驱动实际订阅的话题名
        self.publisher_ = self.create_publisher(JointState, '/allegro_hand/joint_cmd', 10)
        
        # 初始化 MediaPipe
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7)
        
        # 启动定时器，定期捕获摄像头并发布
        self.cap = cv2.VideoCapture(0)
        self.create_timer(0.03, self.timer_callback) # 约 30fps
        self.get_logger().info('MediaPipe ROS2 Bridge 节点已启动！')

    def calculate_angle(self, v1, v2):
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        return np.arccos(np.clip(dot_product / (norm_v1 * norm_v2), -1.0, 1.0))

    def timer_callback(self):
        success, image = self.cap.read()
        if not success:
            return

        image = cv2.flip(image, 1)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)

        # 初始化 16 个关节的角度数组（Allegro Hand v4 通常有 4根手指 * 4关节 = 16自由度）
        # 默认全部给 0.0 弧度
        joint_positions = [0.0] * 16

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # 提取食指关键点
                p5 = np.array([hand_landmarks.landmark[5].x, hand_landmarks.landmark[5].y, hand_landmarks.landmark[5].z])              
                p6 = np.array([hand_landmarks.landmark[6].x, hand_landmarks.landmark[6].y, hand_landmarks.landmark[6].z])
                p7 = np.array([hand_landmarks.landmark[7].x, hand_landmarks.landmark[7].y, hand_landmarks.landmark[7].z])
                p8 = np.array([hand_landmarks.landmark[8].x, hand_landmarks.landmark[8].y, hand_landmarks.landmark[8].z])
                
                v1 = p7 - p6
                v2 = p8 - p7
                angle_rad = self.calculate_angle(v1, v2)
                #self.get_logger().info(f"Calculated angle: {np.degrees(angle_rad)} degrees")
                # 映射到真机安全范围，假设食指中节关节是下标 5
                target_joint = float(np.clip(angle_rad, 0.0, 1.0))  # 假设安全范围是 0 到 1 弧度
                joint_positions[5] = target_joint 

        # 构建并发布 ROS 2 消息
        msg = JointState()
        msg.position = joint_positions
        self.publisher_.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = MediaPipeAllegroBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cap.release()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()