

from __future__ import print_function

from dronekit import connect, VehicleMode, LocationGlobalRelative, LocationGlobal, Command
import time
import math
from pymavlink import mavutil

from firebase import firebase  
import urllib3, urllib, http.client
import json
from datetime import datetime

import cv2
import numpy as np
import keras
model = keras.models.load_model("final_model_3.model")

#Set up option parsing to get connection string
import argparse  
parser = argparse.ArgumentParser(description='Demonstrates basic mission operations.')
parser.add_argument('--connect', 
                   help="vehicle connection target string. If not specified, SITL automatically started and used.")
args = parser.parse_args()
    
connection_string = args.connect
sitl = None

#Initialising the camera
cap = cv2.VideoCapture(0)
print("Started Camera")

#Start SITL if no connection string specified
if not connection_string:
    import dronekit_sitl
    sitl = dronekit_sitl.start_default()
    connection_string = sitl.connection_string()

firebase = firebase.FirebaseApplication('https://inter-iit-drdo-sase-2019.firebaseio.com/', None)
count1 = 0
obj_detected = False

# Connect to the Vehicle
print('Connecting to vehicle on: %s' % connection_string)
vehicle = connect(connection_string, wait_ready=True, baud=57600)

final_height = 2
vehicle.parameters['WPNAV_SPEED'] = 100    

xx = [0, 29.867780, 29.867473, 29.867475, 29.867783]
yy = [0, 77.89834, 77.898342, 77.8984853, 77.89849]

def get_location_metres(original_location, dNorth, dEast):
    """
    Returns a LocationGlobal object containing the latitude/longitude `dNorth` and `dEast` metres from the 
    specified `original_location`. The returned Location has the same `alt` value
    as `original_location`.

    The function is useful when you want to move the vehicle around specifying locations relative to 
    the current vehicle position.
    The algorithm is relatively accurate over small distances (10m within 1km) except close to the poles.
    For more information see:
    http://gis.stackexchange.com/questions/2951/algorithm-for-offsetting-a-latitude-longitude-by-some-amount-of-meters
    """
    earth_radius=6378137.0 #Radius of "spherical" earth
    #Coordinate offsets in radians
    dLat = dNorth/earth_radius
    dLon = dEast/(earth_radius*math.cos(math.pi*original_location.lat/180))

    #New position in decimal degrees
    newlat = original_location.lat + (dLat * 180/math.pi)
    newlon = original_location.lon + (dLon * 180/math.pi)
    return LocationGlobal(newlat, newlon,original_location.alt)


def get_distance_metres(aLocation1, aLocation2):
    """
    Returns the ground distance in metres between two LocationGlobal objects.

    This method is an approximation, and will not be accurate over large distances and close to the 
    earth's poles. It comes from the ArduPilot test code: 
    https://github.com/diydrones/ardupilot/blob/master/Tools/autotest/common.py
    """
    dlat = aLocation2.lat - aLocation1.lat
    dlong = aLocation2.lon - aLocation1.lon
    return math.sqrt((dlat*dlat) + (dlong*dlong)) * 1.113195e5



def distance_to_current_waypoint():
    """
    Gets distance in metres to the current waypoint. 
    It returns None for the first waypoint (Home location).
    """
    nextwaypoint = vehicle.commands.next
    if nextwaypoint==0:
        return None
    missionitem=vehicle.commands[nextwaypoint-1] #commands are zero indexed
    lat = missionitem.x
    lon = missionitem.y
    alt = missionitem.z
    targetWaypointLocation = LocationGlobalRelative(lat,lon,alt)
    distancetopoint = get_distance_metres(vehicle.location.global_frame, targetWaypointLocation)
    return distancetopoint


def download_mission():
    """
    Download the current mission from the vehicle.
    """
    cmds = vehicle.commands
    cmds.download()
    cmds.wait_ready() # wait until download is complete.

def zigzag(aLocation, north, east, height):

    """
    Adds a takeoff command and four waypoint commands to the current mission. 
    The waypoints are positioned to form a square of side length 2*aSize around the specified LocationGlobal (aLocation).

    The function assumes vehicle.commands matches the vehicle mission state 
    (you must have called download at least once in the session and after clearing the mission)
    """	

    cmds = vehicle.commands

    print(" Clear any existing commands")
    cmds.clear() 
    
    print(" Define/add new commands.")
    # Add new commands. The meaning/order of the parameters is documented in the Command class. 
     
    #Add MAV_CMD_NAV_TAKEOFF command. This is ignored if the vehicle is already in the air.
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 0, height))

    #Define the four MAV_CMD_NAV_WAYPOINT locations and add the commands
    point1 = get_location_metres(aLocation,  north, 0)
    point2 = get_location_metres(point1, 0, east)
    point3 = get_location_metres(point2, -north, 0)
    point4 = get_location_metres(point3, 0, east)
    point5 = get_location_metres(point4,  north, 0)
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, point1.lat, point1.lon, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, point2.lat, point2.lon, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, point3.lat, point3.lon, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, point4.lat, point4.lon, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, point5.lat, point5.lon, height))
    #add dummy waypoint "5" at point 4 (lets us know when have reached destination)
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, point5.lat, point5.lon, height))    

    print(" Upload new commands to vehicle")
    cmds.upload()

def move_left(height):

    """
    Adds a takeoff command and four waypoint commands to the current mission. 
    The waypoints are positioned to form a square of side length 2*aSize around the specified LocationGlobal (aLocation).

    The function assumes vehicle.commands matches the vehicle mission state 
    (you must have called download at least once in the session and after clearing the mission)
    """	

    cmds = vehicle.commands

    print(" Clear any existing commands")
    cmds.clear() 
    
    print(" Define/add new commands.")
    # Add new commands. The meaning/order of the parameters is documented in the Command class. 
     
    #Add MAV_CMD_NAV_TAKEOFF command. This is ignored if the vehicle is already in the air.
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, 0, height))

    #Define the four MAV_CMD_NAV_WAYPOINT locations and add the commands
    point1 = LocationGlobal(29.867521, 77.899015, height)
    point2 = LocationGlobal(29.867889, 77.899059, height)

    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[1], yy[1], height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[2], yy[2], height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[2] + (xx[3] - xx[2])/5, yy[2] + (yy[3] - yy[2])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[1] + (xx[4] - xx[1])/5, yy[1] + (yy[4] - yy[1])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[1] + 2*(xx[4] - xx[1])/5, yy[1] + 2*(yy[4] - yy[1])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[2] + 2*(xx[3] - xx[2])/5, yy[2] + 2*(yy[3] - yy[2])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[2] + 3*(xx[3] - xx[2])/5, yy[2] + 3*(yy[3] - yy[2])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[1] + 3*(xx[4] - xx[1])/5, yy[1] + 3*(yy[4] - yy[1])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[1] + 4*(xx[4] - xx[1])/5, yy[1] + 4*(yy[4] - yy[1])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[2] + 4*(xx[3] - xx[2])/5, yy[2] + 4*(yy[3] - yy[2])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[2] + 5*(xx[3] - xx[2])/5, yy[2] + 5*(yy[3] - yy[2])/5, height))
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[1] + 5*(xx[4] - xx[1])/5, yy[1] + 5*(yy[4] - yy[1])/5, height))
    #add dummyy waypoint "5" at point 4 (lets us know when have reached destination)
    cmds.add(Command( 0, 0, 0, mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, 0, 0, xx[1] + 5*(xx[4] - xx[1])/5, yy[1] + 5*(yy[4] - yy[1])/5, height))

    print(" Upload new commands to vehicle")
    cmds.upload()

def arm_and_takeoff(aTargetAltitude):
    """
    Arms vehicle and fly to aTargetAltitude.
    """

    print("Basic pre-arm checks")
    # Don't let the user try to arm until autopilot is ready
    while not vehicle.is_armable:
        print(" Waiting for vehicle to initialise...")
        time.sleep(1)

        
    print("Arming motors")
    # Copter should arm in GUIDED mode
    vehicle.mode = VehicleMode("GUIDED")
    vehicle.armed = True

    while not vehicle.armed:      
        print(" Waiting for arming...")
        time.sleep(1)

    print("Taking off!")
    vehicle.simple_takeoff(aTargetAltitude) # Take off to target altitude

    # Wait until the vehicle reaches a safe height before processing the goto (otherwise the command 
    #  after Vehicle.simple_takeoff will execute immediately).
    while True:
        print(" Altitude: ", vehicle.location.global_relative_frame.alt)      
        if vehicle.location.global_relative_frame.alt>=aTargetAltitude*0.95: #Trigger just below target alt.
            print("Reached target altitude")
            break
        time.sleep(1)

def update_firebase(count):
    lat=vehicle.location.global_relative_frame.lat 
    lon=vehicle.location.global_relative_frame.lon 
    firebase.put('/drone2/obj'+str(count),"lat",lat)
    firebase.put('/drone2/obj'+str(count),"lng",lon)
    firebase.put('/',"count2",count)   

        
print('Create a new mission (for current location)')
move_left(final_height)

ground_signal = 0

while(ground_signal == 0):
    ground_signal = firebase.get('/init2', None)
    print("Waiting for ground signal...")  
    num_sat = int(str(vehicle.gps_0).split('=')[2])
    firebase.put('/', "sat2", num_sat)
    time.sleep(1)

#opening a file for writing
fff = open("gps_sec.txt", "w")

# From Copter 3.3 you will be able to take off using a mission item. Plane must take off using a mission item (currently).
arm_and_takeoff(final_height)

print("Starting mission")
# Reset mission set to first (0) waypoint
vehicle.commands.next=0

# Set mode to AUTO to start mission
vehicle.mode = VehicleMode("AUTO")

gps_print_timer = time.time()

start_time = time.time()
first_line = "start_time: " + str(datetime.now()) + "\n"
fff.write(first_line)  
print_timer = time.time()


# Monitor mission. 
# Demonstrates getting and setting the command number 
# Uses distance_to_current_waypoint(), a convenience function for finding the 
#   distance to the next waypoint.

while True:

    if((time.time() - gps_print_timer) >= 1):
        current_time = time.time() - start_time 
        gps_string = "time: " + str(current_time) + " " + str(vehicle.location.global_relative_frame) + "\n"
        fff.write(gps_string)
        gps_print_timer = time.time()

    nextwaypoint=vehicle.commands.next

    if((time.time() - print_timer) > 1):
        print('Distance to waypoint (%s): %s' % (nextwaypoint, distance_to_current_waypoint()))
        print('Height:', vehicle.location.global_relative_frame.alt)
        print_timer = time.time()
  
    #< Image Processing
    ret, frame = cap.read()
#    cv2.imshow('frame', frame)
    img=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)

    img=cv2.resize(img,(256,256))
    img=(img.astype(np.float32)/255)
    img=np.expand_dims(img, axis=0)
    predictions=model.predict(img,verbose=0)

    y_pred_binary = (predictions > 0.5).astype(np.int)

    if (y_pred_binary==1 and prev_detection==0):
        prev_detection = 1
        print("****************************************")
        print("----------------------------------------")
        print("          Object Detected")
        print("----------------------------------------")
        print("****************************************")
        print("****************************************")
        print("----------------------------------------")
        print("At GPS location: ", vehicle.location.global_relative_frame)
        print("----------------------------------------")
        print("****************************************")

        # firebase update
        count1=count1+1
        update_firebase(count1)
    elif (y_pred_binary==1 and prev_detection==1):
        prev_detection = 1
    else:
        prev_detection = 0
    # />

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    if nextwaypoint==13 : #Dummy waypoint - as soon as we reach waypoint 4 this is true and we exit.
        print("Exit 'standard' mission when start heading to final waypoint (5)")
        break;

print("changed to LAND Mode")
vehicle.mode = VehicleMode("LAND")


#Close vehicle object before exiting script
print("Close vehicle object")
vehicle.close()

# Shut down simulator if it was started.
if sitl is not None:
    sitl.stop()

# Close camera
cap.release()
cv2.destroyAllWindows()
