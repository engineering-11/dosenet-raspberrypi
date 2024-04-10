import matplotlib as mpl
import folium
from folium.plugins import FloatImage
import os
import time
import pika
import sys
#from Adafruit_BME280 import *
#BME280_OSAMPLE_8 = 4
import json
#import gps
import traceback
from PIL import Image
import pexpect

import csv

sys.path.insert(0, 'folium')
sys.path.insert(0, 'branca')

import branca
from branca.element import MacroElement

from jinja2 import Template

print("Starting map_plot.py. :)")

class BindColormap(MacroElement): # Allows colormap to be directly tied to the layer that contains its points
    """Binds a colormap to a given layer.

    Parameters
    ----------
    colormap : branca.colormap.ColorMap
        The colormap to bind.
    """
    def __init__(self, layer, colormap):
        super(BindColormap, self).__init__()
        self.layer = layer
        self.colormap = colormap
        self._template = Template(u"""
        {% macro script(this, kwargs) %}
            {{this.colormap.get_name()}}.svg[0][0].style.display = 'block';
            {{this._parent.get_name()}}.on('overlayadd', function (eventLayer) {
                if (eventLayer.layer == {{this.layer.get_name()}}) {
                    {{this.colormap.get_name()}}.svg[0][0].style.display = 'block';
                }});
            {{this._parent.get_name()}}.on('overlayremove', function (eventLayer) {
                if (eventLayer.layer == {{this.layer.get_name()}}) {
                    {{this.colormap.get_name()}}.svg[0][0].style.display = 'none';
                }});
        {% endmacro %}
        """)  # noqa

def sendmsg(ID,cmd,queue):
	'''
	Sends a message through the selected queue with the given ID.
	'''
	connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
	channel = connection.channel()

	channel.queue_declare(queue=queue)
	channel.basic_publish(exchange='', routing_key=queue, body=json.dumps({'id':ID, 'cmd':cmd}))
	connection.close()

def receive(ID, queue):
	'''
	Returns command or data from queue with given ID. If given ID is None, then returns first message from queue.
	'''
	connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
	channel = connection.channel()
	channel.queue_declare(queue=queue)
	method_frame, header_frame, body = channel.basic_get(queue=queue)
	if body is not None:
		message = json.loads(body.decode('utf-8'))
		if ID == None:
			channel.basic_ack(delivery_tag=method_frame.delivery_tag)
			connection.close()
			return message
		elif message['id'] == ID:
			channel.basic_ack(delivery_tag=method_frame.delivery_tag)
			connection.close()
			if 'cmd' in message:
				return message['cmd']
			elif 'data' in message:
				return message['data']
			else:
				return None
		else:
			connection.close()
			return None
	else:
		connection.close()
		return None

def receive_last_message(ID, queue, message=''):
	'''
	Returns last consecutive message with matching ID.
	'''
	body = receive(ID, queue)
	while body != None:
		message = body
		body = receive(ID, queue)
	return message

def popuptext(sensor_chosen):
	'''
	Formats text for popup labels
	'''
	# List for popup label (current time and values)
	popup = "Time: " + str(time.ctime(time.time())) + '<br>'
	
	for sensor in active_sensors: 
		if sensor == sensor_chosen:
			popup = popup + sensor + " (shown): "
		else:
			popup = popup + sensor + ": "

		popup = popup + str(sensor_dict[sensor]['val']) + "<br>"
			
	return popup # Joins the list of popup labels into a string

def establish_dict():
	'''
	Establishes dictionary of data points.
	'''
	sensor_dict = {}
	radiationRunning = False
	
	for sensor in active_sensors:
		if sensor == 'Air Quality PM 2.5 (ug/m3)':
			sensor_dict['Air Quality PM 2.5 (ug/m3)'] = {'min': 0, 'max':20, 'fg': '','val':0}		
			print("Starting air quality sensor!")
			os.system('python /home/pi/dosenet-raspberrypi-1/air_quality_DAQ.py -i ' + str(int(time_delay * 0.5)) + ' &')
			sendmsg('Air Quality', 'START', 'fromGUI')
			
		elif sensor == 'CO2 (ppm)':
			sensor_dict['CO2 (ppm)'] = {'min': 300, 'max':1000, 'fg': '','val':0,'cm': ''}
			os.system('python /home/pi/dosenet-raspberrypi-1/adc_DAQ.py -i ' + str(int(time_delay * 0.5)) + ' &')
			sendmsg('CO2', 'START', 'fromGUI')
			
		elif sensor == 'Humidity (%)':
			sensor_dict['Humidity (%)'] = {'min': 30, 'max':80, 'fg': '','val':0,'cm': ''}
			os.system('python /home/pi/dosenet-raspberrypi-1/weather_rabbitmq_DAQ.py -i ' + str(int(time_delay * 0.5)) + ' &')
			sendmsg('P/T/H', 'START', 'fromGUI')
					
		elif sensor == 'Pressure (Pa)':
			sensor_dict['Pressure (Pa)'] = {'min': 99500, 'max':101400, 'fg': '','val':0,'cm': ''}
			os.system('python /home/pi/dosenet-raspberrypi-1/weather_rabbitmq_DAQ.py -i ' + str(int(time_delay * 0.5)) + ' &')
			sendmsg('P/T/H', 'START', 'fromGUI')
				
		elif sensor == 'Radiation (cps)':
			sensor_dict['Radiation (cps)'] = {'min': 0, 'max':100, 'fg': '','val':0,'cm': ''}			
		
		elif sensor == 'Radiation Bi (cps)':
			sensor_dict['Radiation Bi (cps)'] = {'min': 0, 'max':15, 'fg': '','val':0,'cm': ''}			
			
		elif sensor == 'Radiation K (cps)':
			sensor_dict['Radiation K (cps)'] = {'min': 0, 'max':15, 'fg': '','val':0,'cm': ''}			
			
		elif sensor == 'Radiation Tl (cps)':
			sensor_dict['Radiation Tl (cps)'] = {'min': 0, 'max':15, 'fg': '','val':0,'cm': ''}			
			
		elif sensor == 'Temperature (C)':
			sensor_dict['Temperature (C)'] = {'min': 15, 'max':30, 'fg': '','val':0,'cm': ''}
			os.system('python /home/pi/dosenet-raspberrypi-1/weather_rabbitmq_DAQ.py -i ' + str(int(time_delay * 0.5)) + ' &')
			sendmsg('P/T/H', 'START', 'fromGUI')
	
		if not radiationRunning and sensor in ['Radiation (cps)', 'Radiation Bi (cps)', 'Radiation K (cps)', 'Radiation Tl (cps)']:
			os.system('sudo python /home/pi/dosenet-raspberrypi-1/D3S_rabbitmq_DAQ.py -i ' + str(time_delay) + ' &')
			print("Started Radiation script!")
			#child.interact()
			sendmsg('Radiation', 'START', 'fromGUI')
			radiationRunning = True
	
	time.sleep(5)
	
	return sensor_dict

def read_data():
	'''
	Reads data into dictionary.
	'''
	data = receive(None, 'toGUI')
	
	while data != None:	# Reads data from queue
		sensor_label = data['id']
		
		if sensor_label == "Air Quality":
			sensor_dict['Air Quality PM 2.5 (ug/m3)']['val'] = data['data'][1][0]
		elif sensor_label == "CO2":
			sensor_dict['CO2 (ppm)']['val'] = data['data'][0]
		elif sensor_label == "P/T/H":
			if 'Humidity (%)' in active_sensors:
				sensor_dict['Humidity (%)']['val'] = data['data'][1][0]
			if 'Pressure (Pa)' in active_sensors:
				sensor_dict['Pressure (Pa)']['val'] = data['data'][2][0]
			if 'Temperature (C)' in active_sensors:
				sensor_dict['Temperature (C)']['val'] = data['data'][0][0]
		elif sensor_label == "Radiation":
			global spectrum
			spectrum = data['data']
			
			if 'Radiation (cps)' in active_sensors:
				counts = 0
				for count in spectrum:
					counts = counts + count
				counts = counts/float(time_delay)
				sensor_dict['Radiation (cps)']['val'] = counts
			
			if 'Radiation Bi (cps)' in active_sensors:
				bismuthCounts = 0
				
				for count in spectrum[850:1100]:
					bismuthCounts = bismuthCounts + count
				bismuthCounts = bismuthCounts/float(time_delay)
				sensor_dict['Radiation Bi (cps)']['val'] = bismuthCounts
				
			if 'Radiation K (cps)' in active_sensors:
				potassiumCounts = 0
				
				for count in spectrum[2000:2400]:
					potassiumCounts = potassiumCounts + count
				potassiumCounts = potassiumCounts/float(time_delay)
				sensor_dict['Radiation K (cps)']['val'] = potassiumCounts
				
			if 'Radiation Tl (cps)' in active_sensors:
				thalliumCounts = 0
				
				for count in spectrum[3600:4000]:
					thalliumCounts = thalliumCounts + count
				thalliumCounts = thalliumCounts/float(time_delay)
				sensor_dict['Radiation Tl (cps)']['val'] = thalliumCounts
		
		elif sensor_label == "GPS":
			global coordinates
			coordinates = data['data']
					
		data = receive(None, 'toGUI')

def create_file():
	'''
	Creates csv file to log data from run - name contains acronym for all sensors used as well as timestamp (zyy of run intialization
	Returns open file and results
	'''
	global file_dict
	
	files = {}
	if file_dict['Log File']['Record']:
		if file_dict['Log File']['Filename'] == '':
			tempfileheader = time.strftime('GPS_GUI_Data_%Y-%m-%d_%H-%M-%S_', time.localtime())
			for letter in active_sensors:
				tempfileheader = tempfileheader + letter[0]
			file_dict['Log File']['Filename'] = tempfileheader
			
		log_out_file = open('/home/pi/data/'+file_dict['Log File']['Filename']+'.csv', "a+", )
		log_results = csv.writer(log_out_file, delimiter = ",")
		log_results.writerow(['Epoch time', 'Latitude', 'Longitude'] + active_sensors)
		
		files['Data Log Out File'] = log_out_file
		files['Data Log Results'] = log_results
	
	if file_dict['Spectrum File']['Record'] and 'Radiation (cps)' in active_sensors:
		if file_dict['Spectrum File']['Filename'] == '':
			file_dict['Spectrum File']['Filename'] = time.strftime('GPS_GUI_Spectrum_Data_%Y-%m-%d_%H-%M-%S', time.localtime())
		spectrum_out_file = open('/home/pi/data/'+file_dict['Spectrum File']['Filename']+'.csv', "a+", )
		spectrum_results = csv.writer(spectrum_out_file, delimiter = ",")
		spectrum_results.writerow(['Epoch time'] + list(range(0,4096)))
		files['Spectrum Out File'] = spectrum_out_file
		files['Spectrum Results'] = spectrum_results
		
	return files

def write_data():
	'''
	Appends row to previously created log file 
	'''
	if file_dict['Log File']['Record']:
		row = [time.time(), coordinates[0], coordinates[1]]
		for sensor in active_sensors:
			print(sensor_dict)
			row.append(sensor_dict[sensor]['val'])
		files['Data Log Results'].writerow(row)
		files['Data Log Out File'].flush()
	
	if file_dict['Spectrum File']['Record'] and 'Radiation (cps)' in active_sensors:
		files['Spectrum Results'].writerow([time.time()] + spectrum)
		

def close_file():
	'''
	Closes the log file
	'''
	if file_dict['Log File']['Record']:
		files['Data Log Out File'].close()
	
	if file_dict['Spectrum File']['Record'] and 'Radiation (cps)' in active_sensors:
		files['Spectrum Out File'].close()
	
	sys.stdout.flush()
	
if __name__ == '__main__':
	try:
		#Initial variables
		sensor_tuple = ('Air Quality PM 2.5 (ug/m3)','CO2 (ppm)', 'Humidity (%)', 'Pressure (Pa)','Radiation (cps)', 'Temperature (C)')
		chunk = [37.875381,-122.259019]
		coordinates = [0, 0]
		spectrum = []
		
		# Gets list of active sensors, time delay, and filename
		active_sensors = receive('Sensors', 'control') # List of active sensors
		time_delay = receive('Time Delay', 'control')
		file_dict = receive('Files', 'control')
		
		sensor_dict = establish_dict() # Establishes a dictionary
		
		files = create_file()
		
		# Starts GPS DAQ
		os.system('python /home/pi/dosenet-raspberrypi-1/updated_gps/gps_daq.py -i' + str(time_delay) + '&')
		
		location = folium.Map(location=chunk,zoom_start = 15) # Fetches chunk
		location.save('map.html')
		
		#os.system('bash /home/pi/launch.sh')
		os.system('xdg-open map.html') # Opens the window containing map
		time.sleep(5)
		os.system('xdotool windowsize `xdotool search --onlyvisible --name "Chromium"` 560 440')
		#os.system('xdotool key Ctrl-l')
		#os.system('xdotool search --onlyvisible --name "Chromium" windowfocus key ctrl-l')
		#os.system('xdotool search --onlyvisible --name "Chromium" windowfocus type "--disable-cache"')
		#os.system('xdotool key Return')

		for key in sensor_dict:	
			sensor_dict[key]['fg'] = folium.FeatureGroup(name=key) # Establishes Feature Groups
			sensor_dict[key]['cm'] = branca.colormap.LinearColormap(['#6801D2','#1996F3','#4Cf2CE','#B3F295','#FF934D','#FF0000'], vmin=sensor_dict[key]['min'], vmax=sensor_dict[key]['max'], caption=key)
		
		shown_sensor = '' # Initializing shown_sensor
		
		while True:
			shown_sensor = receive_last_message('Shown Sensor', 'control', shown_sensor) # Gets the chosen sensor to visualize
			
			if receive_last_message('EXIT', 'control') == 'EXIT': # Looks for EXIT command
				break
			
			read_data() # IMPORTANT FUNCTION -- Reads the data from queue
			
			# Recenters chunk
			if coordinates != [0, 0]:
				chunk = coordinates
			
			location = folium.Map(location=chunk,zoom_start = 10)
			
			for key in sensor_dict:
				sensor_dict[key]['fg'].show =  (bool(key == shown_sensor)) # Sets the selected sensor to visible
				
				# Adds feature groups and color maps to map again
				location.add_child(sensor_dict[key]['fg'])
				location.add_child(sensor_dict[key]['cm'])
				location.add_child(BindColormap(sensor_dict[key]['fg'], sensor_dict[key]['cm'])) # Binds colormap to feature group

				# Gets point color
				point_color = mpl.colors.rgb2hex(sensor_dict[key]['cm'].rgba_floats_tuple(sensor_dict[key]['val']))
				
				# Plots Circle
				folium.Circle(radius = 15, location=coordinates, popup = popuptext(key),
							fill_color = point_color,color = '#000000',fill_opacity = 1,stroke = 1,weight = 1).add_to(sensor_dict[key]['fg'])
		
			location.add_child(folium.map.LayerControl()) # Adds layer control
			
			write_data() # Writes data into files
				
			location.save('map.html') # Saves map as html
			
			os.system('xdotool search --onlyvisible --name "Chromium" windowfocus key --clearmodifiers ctrl+r') # Reloads page
			
			time.sleep(time_delay)
	finally:
		close_file() # Closes files
		
		os.system('xdotool search --onlyvisible --name "Chromium" windowfocus key --clearmodifiers ctrl+w') # Closes window after exit
		
		# Sends exit commands to daqs
		print("Sending EXIT to active_sensors:",active_sensors)
		for sensor in active_sensors:
			print("Sending EXIT to ", sensor)
			if sensor in ['Temperature (C)', 'Humidity (%)', 'Pressure (Pa)']:
				sendmsg('P/T/H', 'EXIT', 'fromGUI')
			elif sensor in ['Radiation (cps)', 'Radiation Bi (cps)', 'Radiation K (cps)', 'Radiation Tl (cps)']:
				sendmsg('Radiation', 'EXIT', 'fromGUI')
			elif sensor=='Air Quality PM 2.5 (ug/m3)':
				sendmsg('Air Quality', 'EXIT', 'fromGUI')
			else:
				sendmsg(sensor,'EXIT','fromGUI')

		sendmsg('GPS', 'EXIT', 'fromGUI')
		
		traceback.print_exc()

# This was made by Big Al and Edward Lee
