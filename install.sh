#DronekitInstallation
sudo apt-get update    #Update the list of packages in the software center
sudo apt-get install python3-dev python3-opencv python3-wxgtk3.0 libxml2-dev python3-pip python3-matplotlib python3-lxml

sudo pip3 install future
sudo pip3 install pymavlink
sudo pip3 install mavproxy
pip install dronekit

If you want to test your mission on SITL then run the following code,
pip install dronekit-sitl


#ObjectDetection
For the object detection part, run the following commands,
sudo pip3 install scikit-learn
sudo pip3 install tensorflow
sudo pip3 install keras
sudo apt-get install build-essential cmake pkg-config
sudo apt-get install libjpeg-dev libtiff5-dev libjasper-dev libpng12-dev
sudo apt-get install libavcodec-dev libavformat-dev libswscale-dev libv4l-dev
sudo apt-get install libxvidcore-dev libx264-dev
sudo apt-get install libgtk2.0-dev libgtk-3-dev
sudo apt-get install libatlas-base-dev gfortran
sudo apt-get install python2.7-dev python3-dev

#Firebase
And finally for the firebase, use
 sudo pip3 install requests==1.1.0
 sudo pip3 install python-firebase


