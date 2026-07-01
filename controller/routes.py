import base64
import datetime
import json
from io import BytesIO
import time
import cv2
from flask import Blueprint, Response, jsonify, request, Flask, send_file
import threading
from drone.camera import start_drone, stop_drone
import numpy as np
from djitellopy import TelloException

from controller.db import db
from controller.util import log as util_log
from drone.config import DEBUG_WEB
from drone.video import video_project, set_video_project
from drone.tello import tello


routes_bp = Blueprint("general routes", __name__)

log = util_log('web')

@routes_bp.route("/register", methods=['POST'])
def register1():
    if request.method != 'POST':
        return Response(status=405)
    
    try:
        data = request.json
        print(data)
        
        _, cursor = db()
        
        query = "INSERT INTO users(firstname, lastname, email, username, password, organization) VALUES(%s,%s,%s,%s,%s,%s)"
        
        cursor.execute(query, (data['firstname'], data['lastname'],data['email'],data['username'],data['password'],data['organization']))
        user_id = cursor.lastrowid
        cursor.execute("commit")
        
        # TODO: Add validation
        return {
            "message": "Success",
            "user_id": user_id
        }
        
    except Exception as e:
        log('[register] Error occured')
        print(e) 
        return jsonify({
                "message": "Error",
                "error": str(e)
            }), 400
    
    

@routes_bp.route('/login', methods=['POST'])
def login():
    if request.method != 'POST':
        return {}, 405

    try:
        data = request.json
        
        _, cursor = db()
        
        # TODO: add encryption
        query = f"SELECT * FROM users WHERE username = '{data['username']}' AND password = '{data['password']}'"
        
        cursor.execute(query)
        
        res = cursor.fetchone()
        
        if not res:
            return {
                "message": "Invalid username or password"
            }, 400
        

        # check status
        if res["status"] == 'pending':
            return {
                "message": "Account has not been approved yet"
            }, 400

        res['profile_image'] =  base64.b64encode(res['profile_image']).decode('utf-8') if res['profile_image'] is not None else ""
        
        
        return {
            "message": "Login Success",
            "user": res
        }, 200
        
        
    except Exception as e:
        log('[login] Error occured')
        print(e) 
        return {
            "message": str(e),
            "error": str(e)
        }, 400


@routes_bp.route('/create_project', methods=['POST'])
def create_project():
    if request.method != 'POST':
        return Response('',status=405)
    
    data = request.json
    
    (_, cursor) = db()
    query = "insert into project(user, name, coordinate, detect) values (%s,%s,%s,%s)"
    cursor.execute(query, (data['user'], data['name'], data['coordinate'], data['detection']))
    project_id = cursor.lastrowid
    
    cursor.execute('commit')
    
    return jsonify({
        "message": "Success",
        "project_id": project_id
    })


def format_results(result):
        ssb64 = base64.b64encode(result['SS'])

        result['SS'] = ssb64.decode('utf-8')
        result['Time'] = result['Time'].strftime('%d/%m/%Y')
        if type(result['location']) != str:

            result['location'] = result['location'].decode('utf-8') if result['location'] is not None else None
        
        return result

@routes_bp.route('/get_snapshot')
def get_snapshot():
    image_ids = request.args.get('id')
    project_id = request.args.get('project')
    
    if not image_ids and not project_id:
        return {"message": "Please provide image ids or project id"}, 400
    
    if image_ids and project_id:
        return {"message": "Provide either project id or image ids only"}, 400
    
    
    _, cur = db()
    
    if image_ids:
        try:
            # convert to array
            
            ids = json.loads(image_ids)
            
            ids = map(lambda x: str(x), ids)
            
            query_ids = "(" + ",".join(ids) + ")"
            
            if query_ids == '()':
                return [], 200
            
            
            query = f'SELECT * FROM img WHERE SSID in {query_ids}'
            cur.execute(query)
            
            results = cur.fetchall()
            
            results = map(format_results, results)
            
            
            return jsonify(list(results)), 200
            
        except json.JSONDecodeError as e:
            return jsonify(e), 400
        except Exception as e:
            return jsonify(e), 500
        
    
    # handle project id
    
    query = "SELECT * FROM img WHERE project_id = %s"
    cur.execute(query, (project_id,))
    results = list(map(format_results, cur.fetchall()))
    
    return jsonify(results), 200
    
    

@routes_bp.route('/check_project')
def check_project():
    project_id = request.args.get('project')
    if not project_id:
        return {}, 404
    
    _, cur = db()
    
    query = f"SELECT * FROM project WHERE id = '{project_id}'"
    cur.execute(query)
    res = cur.fetchone()
    if not res:
        return {}, 404
    
    return res, 200

@routes_bp.route('/notification')
def notification():
    
    project_id = request.args.get('project')
    after = request.args.get('after')
    
    if not project_id:
        return {}, 400
    
    _, cur = db()
    
    query = "SELECT * FROM notification WHERE project_id = %s"
    
    if after:
        query += " AND id > %s"
        cur.execute(query, (project_id,after))
    else:
        cur.execute(query, (project_id,))
    
    results = cur.fetchall()
    
    return jsonify(results), 200

@routes_bp.route('/image/<int:img_id>.jpeg')
def get_image(img_id):
    
    if not img_id:
        return {"message": "Please provide an image"}, 400
    
    # get image from database
    print(img_id)
    try:
        query = "SELECT * FROM img WHERE SSID = %s"
        _, cur = db()
        
        cur.execute(query, (img_id,))

        res = cur.fetchone()
        
        if not res:
            return Response(status=404)
        
        image_bytes = BytesIO(res['SS'])
        
        return send_file(image_bytes, mimetype="image/jpeg")
        
    except Exception as e:
        print(e)
        return {"message": "Internal server error"}, 500
    
@routes_bp.route("/ping", methods=["GET", "POST"])
def ping():
    print(request.json)
    return {"message": "Pong"}, 200

@routes_bp.route('/project_list')
def project_list():
    try:
        
        user = request.args.get('user')
        
        if not user:
            return {"message": "No user"}, 400
        
        query = "SELECT * FROM project WHERE user = %s"
        
        _, cur = db()
        
        cur.execute(query, (user,))
        
        res = cur.fetchall()
        
        return res, 200
    except Exception as e:
        print(e)
        return {"error": e}, 500
    
@routes_bp.route("/update_user", methods=["POST"])
def update_user():
    if request.method != 'POST':
        return {}, 405
    
    
    id = request.form.get('id')
    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    email = request.form.get('email')
    organization = request.form.get('organization')
    username = request.form.get('username')
    password = request.form.get('password')
    
    profile_pic = request.files.get('profile-pic')
    profile_bytes = profile_pic.read()
    
    log('pw', password)
    
    
    
    if len(profile_bytes) > 0:
        # thre is picture
        # update picture first
        profile_bytes = np.frombuffer(profile_bytes, np.uint8)
        image = cv2.imdecode(profile_bytes, cv2.IMREAD_COLOR)
        
        # Convert to JPEG if necessary
        if profile_pic.content_type != 'image/jpeg':
            _, jpeg_data = cv2.imencode('.jpg', image)
            jpeg_data = jpeg_data.tobytes()
        else:
            jpeg_data = profile_bytes.tobytes()
        _, cur = db()
            
        cur.execute("UPDATE users SET profile_image = %s WHERE id = %s", (jpeg_data, id))
        cur.execute("commit")
        
        
    _, cur = db()
    # update all user data
    query = f"UPDATE users SET firstname = %s, lastname = %s, email = %s, organization = %s, username = %s{', password = %s' if password is not None and len(password) > 0 else ''} WHERE id = %s"
    log(query)
    if password is not None and len(password) > 0:
        cur.execute(query, (firstname, lastname, email, organization, username, password, id))
    else:
        cur.execute(query, (firstname, lastname, email, organization, username, id))
        
    cur.execute("commit")
    
    # user data
    cur.execute("SELECT * FROM users WHERE id = %s", (id,))
    res = cur.fetchone()
    
    res = format_user(res)
        
    log(res)
    
    return res, 200

def format_user(res):
    res['profile_image'] = base64.b64encode(res['profile_image']).decode('utf-8') if res['profile_image'] is not None else None
    return res 

@routes_bp.route('/update_project', methods=['POST'])
def update_project():
    if request.method != 'POST':
        return {}, 405
    
    data = request.json
    
    query = 'UPDATE project SET name = %s, coordinate = %s, detect = %s WHERE id = %s'
    
    _, cur = db()
    cur.execute(query, (data['name'], data['coordinate'], data['detect'], data['id']))
    
    cur.execute("commit")
    
    return data, 200

drone_thread = None
drone_running = False
movements = []
start_time = None
project = None

@routes_bp.route('/start_drone')
def start_drone_route():
    global drone_thread, drone_running, tello, movements, video_project, start_time, project
    
    project_id = request.args.get('project')
    mode = request.args.get('mode')  # Get mode from the request

    if not project_id:
        return {"message": "Invalid project"}, 400

    if drone_running:
        print('botak gay')
        return jsonify({"message": "Drone is already running"}), 400

    # data = request.json
    # project_id = data.get('project_id', 12)  # Default project ID

    drone_running = True
    start_time = int(time.time())
    project =project_id
    set_video_project(project_id)

    # drone_thread = threading.Thread(target=start_drone, args=(tello,project_id,), daemon=True)
    # drone_thread.start()

    start_drone(tello,project_id, mode)
    return jsonify({"message": "Drone started successfully"}), 200

@routes_bp.route('/check_running')
def check_running():
    global drone_running, start_time, project

    project_id = request.args.get('project')




    if drone_running and project_id == project:
        return {
            "message": True,
            "time": start_time
        }, 200
    else:
        return {
            "message": False
        }, 200

@routes_bp.route('/stop_drone')
def stop_drone_route():
    global drone_running, tello, movements, video_project, drone_thread

    set_video_project(None)

    if not drone_running:
        print('Drone is not running')
        return jsonify({"message": "Drone is not running"}), 400

    drone_running = False

    if drone_thread is not None:
        print('Joining drone thread...')
        drone_thread.join()
        print('Drone thread joined.')

    print(f"Tello object: {tello}")

    def stop_drone_thread():
        try:
            stop_drone(tello, movements)
            print('Drone stopped successfully.')
        except TelloException as e:
            print(f"Error stopping drone: {e}")

    stop_thread = threading.Thread(target=stop_drone_thread)
    stop_thread.start()

    return jsonify({"message": "Drone stop initiated"}), 200

@routes_bp.route('/update_timer')
def update_timer():
    project_id = request.args.get('project')
    timer = request.args.get('timer')
    
    if not project_id:
        return {}, 400
    
    query = "UPDATE project SET timer = %s WHERE id = %s"
    
    try:
        _, cur = db()
        
        cur.execute(query, (timer,project_id))
        cur.execute("commit")
        
        return {}, 200
        
    except Exception as e:
        log(e)
        return {"error": str(e)}, 500
    

@routes_bp.route("/users")
def get_users():
    try:
        _,cur = db()
        cur.execute("SELECT * FROM users")
        res = cur.fetchall()

        res = list(map(format_user, res))

        return res, 200
    except Exception as e:
        print("error at get users")
        print(e)
        return {
            "message": "Failed to get users"
        }, 500

@routes_bp.route("/approve_user", methods=["POST"])
def approve_user():
    log = util_log("approve_user")
    if request.method != "POST":
        return {
            "message": "Invalid reqeust"
        }, 405
    user_id = request.args.get("user")
    
    if not user_id:
        return {
            "message": "Invalid request"
        }, 400
    
    try:
        _,cur = db()
        query = "UPDATE users SET status = 'approved' WHERE id = %s"
        cur.execute(query, (user_id,))
        cur.execute("commit")
        return {
            "message": "Approved success"
        }, 200
    
    except Exception as e:
        log(e)
        return {
            "message": "Failed to approve user"
        }, 500
    

@routes_bp.route("/reject_user")
def reject_user():
    user_id = request.args.get('user')

    if not user_id:
        return {
            "message": "Please provide user id"
        }, 400
    
    query = "DELETE FROM users WHERE id = %s"
    try:
        _, cur = db()

        cur.execute(query, (user_id,))
        cur.execute('commit')

        return {
            "message": "Successful"
        }, 200
        
    except Exception as e:
        print('reject user', e)
        return {
            'message': 'Failed to delete user'
        }, 500