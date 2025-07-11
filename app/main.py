import numpy as np
from cv2.typing import MatLike
from layers.infraestructure.video_analysis.plotting.drawer_factory import DrawerFactory
from layers.infraestructure.video_analysis.trackers.tracker import Tracker
import json

from layers.infraestructure.video_analysis.services.video_processing_service import (
    read_video, save_video)
from layers.infraestructure.video_analysis.camera_movement_estimator.camera_movement_estimator import CameraMovementEstimator
from layers.infraestructure.video_analysis.player_ball_assigner.player_ball_assigner import PlayerBallAssigner
from layers.infraestructure.video_analysis.speed_and_distance_estimator.speed_and_distance_estimator import SpeedAndDistance_Estimator
from layers.infraestructure.video_analysis.team_assigner.team_assigner import TeamAssigner
from layers.infraestructure.video_analysis.view_transformer.view_transformer import ViewTransformer
from layers.infraestructure.video_analysis.plotting.voronoi_diagram_drawer import VoronoiDiagramDrawer
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()  # Convert NumPy arrays to Python lists
        elif isinstance(obj, np.generic):
            return obj.item()  # Convert NumPy scalar types to native Python types
        return json.JSONEncoder.default(self, obj)


def main():
    # Read Video
    video_frames: list[MatLike] = read_video('./res/input_videos/08fd33_4.mp4') # Colocar el path del video

    # Initialize Tracker
    version = 11 
    size = 'n' # puede ser 'n', 's', 'm', 'l', 'x'
    tracker = Tracker(f'./res/models/yolo{version}{size}.pt')

    tracks = tracker.get_object_tracks(
        video_frames,
        read_from_stub=True,
        stub_path='./res/stubs/track_stubs.pkl')
    
    # Get object positions 
    tracker.add_position_to_tracks(tracks)

    # camera movement estimator
    camera_movement_estimator = CameraMovementEstimator(video_frames[0])
    camera_movement_per_frame = camera_movement_estimator.get_camera_movement(
        video_frames,
        read_from_stub=True,
        stub_path='./res/stubs/camera_movement_stub.pkl')
    camera_movement_estimator.add_adjust_positions_to_tracks(tracks, camera_movement_per_frame)


    # View Trasnformer
    view_transformer = ViewTransformer()
    view_transformer.add_transformed_position_to_tracks(tracks)

    # Interpolate Ball Positions
    tracks["ball"] = tracker.interpolate_ball_positions(tracks["ball"])

    # Speed and distance estimator
    speed_and_distance_estimator = SpeedAndDistance_Estimator()
    speed_and_distance_estimator.add_speed_and_distance_to_tracks(tracks)

    # Assign Player Teams
    team_assigner = TeamAssigner()
    team_assigner.assign_team_color(
        video_frames[0], 
        tracks['players'][0])
    
    for frame_num, player_track in enumerate(tracks['players']):
        for player_id, track in player_track.items():
            team = team_assigner.get_player_team(
                video_frames[frame_num],   
                track['bbox'],
                player_id)
            tracks['players'][frame_num][player_id]['team'] = team 
            tracks['players'][frame_num][player_id]['team_color'] = team_assigner.team_colors[team]

    
    # Assign Ball Aquisition
    player_assigner = PlayerBallAssigner()
    team_ball_control= []
    for frame_num, player_track in enumerate(tracks['players']):
        ball_bbox = tracks['ball'][frame_num][1]['bbox']
        assigned_player = player_assigner.assign_ball_to_player(player_track, ball_bbox)

        if assigned_player != -1:
            tracks['players'][frame_num][assigned_player]['has_ball'] = True
            team_ball_control.append(tracks['players'][frame_num][assigned_player]['team'])
        else:
            team_ball_control.append(team_ball_control[-1])
    team_ball_control= np.array(team_ball_control)

    # Voronoi Diagram Drawer
    try:
        DrawerFactory.run_drawer(
            'voronoi',
            tracks['players']
        )
        DrawerFactory.run_drawer(
            'heatmap',
            tracks['players']
        )
    except Exception as e:
        print(f"Error drawing Voronoi diagram: {e}")

    with open("tracks.json", "w") as f:
        try:
            f.write(json.dumps(tracks['players'], cls=NumpyEncoder, indent=2))
        except TypeError as e:
            f.write(str(tracks))
            


    # Draw output 
    ## Draw object Tracks
    output_video_frames = tracker.draw_annotations(video_frames, tracks,team_ball_control)

    ## Draw Camera movement
    output_video_frames = camera_movement_estimator.draw_camera_movement(output_video_frames,camera_movement_per_frame)

    ## Draw Speed and Distance
    speed_and_distance_estimator.draw_speed_and_distance(output_video_frames, tracks)

    # Save video
    save_video(output_video_frames, './res/output_videos/output_video.avi')

if __name__ == '__main__':
    main()