from setuptools import find_packages, setup

package_name = 'mediapipe_test'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='fzc',
    maintainer_email='fzc@todo.todo',
    description='TODO: Package description',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'mediapipe_allegro_bridge = mediapipe_test.mediapipe_node:main',
            'point_visual = mediapipe_test.point_visual:main',
        ],
    },
)
