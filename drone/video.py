import time
import cv2
from djitellopy import TelloException
from flask import Blueprint, Response, request
from controller.db import db
from controller.util import log as util_log
from drone.camera import CLASS_NAMES, add_actions
from drone.config import DEBUG_VIDEO
from drone.detection import detect_person
from drone.location import get_location
from drone.yolo import model
from drone.tello import tello


video_bp = Blueprint("Video BP", __name__)

if DEBUG_VIDEO:
    cap = cv2.VideoCapture(0)

@video_bp.route("/video_feed")
def video_feed():
    global latest_frame, video_project, video_start, frame_queue
    project_id = request.args.get('project')
    check_status = request.args.get('status')
    
    # print(check_status)
    if check_status is not None:
        return {
            "video_start": video_start,
            "project": video_project }, 200
    
    video_project = project_id
    
    VIDEO_TIMEOUT = 15000
    log = util_log('web video')

    
    def generate():
        last_try = None
        
        while True:
            if latest_frame is None:
                if last_try is None:
                    last_try = time.time() * 1000
                    
                # check for timeout
                elapsed = time.time() * 1000 - last_try
                
                if elapsed > VIDEO_TIMEOUT:
                    log('TIMEOUT!')
                    break
                
                time.sleep(0.1)
                continue
            else:
                last_try = None
            
            
            time.sleep(0.05)
            yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + latest_frame.tobytes() + b'\r\n\r\n')
            
            
        

    response = Response(generate(),  mimetype="multipart/x-mixed-replace;boundary=frame")
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


def upload_image( project_id: int, id: int, image_bytes, conf: float):
    
    current_location = get_location()
    
    img_query = "INSERT INTO img (project_id, SS, Confidence, location) VALUES (%s,%s, %s, %s)"
    noti_query = "INSERT INTO notification (project_id, img_id) VALUES (%s,%s)"
    
    try:
        _, cur = db()
        
        print("updating db")
        cur.execute(img_query, (project_id, image_bytes, conf,  current_location if current_location is not None else None))

        img_id = cur.lastrowid
        
        cur.execute(noti_query, (project_id, img_id))
        
        cur.execute('commit')
        
    except Exception as e:
        print(e)
        
if DEBUG_VIDEO:
    cap = cv2.VideoCapture(0)
     
def get_frame(tello):
    if DEBUG_VIDEO:
        _, frame = cap.read()
        return frame
    
    frame = tello.get_frame_read().frame
    return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        

latest_frame = None
tracked_objects = list()
video_project = None
video_start = False
project_data = None
def set_video_project(id):
    global video_project, project_data
    video_project = id
    
    if video_project is None:
        project_data = None
        return
    _, cur = db()
    # get project data
    cur.execute("SELECT * FROM project WHERE id = %s", (video_project,))
    res = cur.fetchone()
    if not res:
        print('cant get project data')
    project_data = res
    print(project_data)

set_video_project(31)

def start_video_thread():
    global latest_frame, tracked_objects, video_project, video_start, project_data
    
    log = util_log('video')
    
    
    if not DEBUG_VIDEO:
        add_actions(['connect','streamon', 'motoron'], first=True)

    
    last_video = None
    
    while True:
        # log('frame: ', latest_frame)
        # log(f'project: {video_project}')
        try:
            if not DEBUG_VIDEO:
                if last_video is None:
                    last_video = time.time() * 1000
                    
                # try to reconnect every 10 seconds
                if time.time() * 1000 -  last_video > 10000:
                    log('reconnect if not')
                    last_video = None # reset try
                    add_actions(['connect','streamon', 'motoron'], first=True)
                    
            frame = get_frame(tello)
            
            detect_type = None

            if project_data:
                to_detect = project_data['detect']


                detect_type = to_detect
                detect_type = list(map(lambda x: int(x), detect_type.split(',')))

            min_threshold = 0.5
                
            results = model.track(frame, persist=True, classes=detect_type, verbose=False, conf=min_threshold)

            person_detected = len(results[0].boxes) > 0
            # person_detected = detect_person(results[0])

            if person_detected:
                output = results[0].plot() 
            else:
                output = frame

            success, jpeg = cv2.imencode('.jpg', output)
            
            if person_detected:
                boxes = results[0].boxes
                # print(tracked_objects)
                for box in boxes:
                    if box.id is None:
                        continue
                    if box.id in tracked_objects:
                        continue
                    
                    tracked_objects.append(box.id.item())
                    
                    # send notification
                    if video_project:
                        upload_image(video_project, box.id, jpeg.tobytes(), box.conf.item())


            if not success:
                print('[video_feed] Frame Dropped')
                continue
            
            latest_frame = jpeg
            video_start = True
            
        except TelloException as e:
            log(e)
            log('wait a bit')
            latest_frame = None
            time.sleep(1)
        except Exception as e:
            log(e)
            time.sleep(1)