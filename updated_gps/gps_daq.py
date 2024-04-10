import json

import pika
import sys
import time
import argparse

import board
import busio
import serial
import adafruit_gps


sys.stdout.flush()

def send_data(data):
	connection = pika.BlockingConnection(
					  pika.ConnectionParameters('localhost'))
	channel = connection.channel()
	channel.queue_declare(queue='toGUI')
	message = {'id': 'GPS', 'data': data}

	channel.basic_publish(exchange='',
						  routing_key='toGUI',
						  body=json.dumps(message))
	connection.close()

def receive(ID, queue):
	'''
	Returns command from queue with given ID
	'''
	connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
	channel = connection.channel()
	channel.queue_declare(queue=queue)
	method_frame, header_frame, body = channel.basic_get(queue=queue)
	if body is not None:
		message = json.loads(body)
		if message['id']==ID:
			channel.basic_ack(delivery_tag=method_frame.delivery_tag)
			connection.close()
			return message['cmd']
		else:
			connection.close()
			return None
	else:
		connection.close()
		return None

if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument("--interval", "-i", type=int, default=1)
	parser.add_argument("--test", "-t", action="store_true", default=False)

	args = parser.parse_args()
	arg_dict = vars(args)
	
	uart = serial.Serial("/dev/ttyUSB0", baudrate=9600, timeout=10)

    # Create a GPS module instance.
	gps = adafruit_gps.GPS(uart, debug=False)  # Use UART/pyserial

    # Turn on the basic GGA and RMC info (what you typically want)
	#gps.send_command(b"PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0")
	# Turn on everything (not all of it is parsed!)
	gps.send_command(b'PMTK314,1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0')

    # Set update rate to once a second (1hz) which is what you typically want.
	gps.send_command(b"PMTK220,500")

    # Main loop runs forever printing the location, etc. every second.
	last_print = time.monotonic()


	while True: # Starts collecting and plotting data
		
		lat, lon = 0, 0
		
		if not arg_dict['test']:
			command = receive('GPS', 'fromGUI')

			if command == 'EXIT':
				print("GPS daq has received command to exit")
				break
		
		gps.update()
        # Every second print out current location details if there's a fix.
		current = time.monotonic()
		if current - last_print >= arg_dict['interval']:
			last_print = current
			if not gps.has_fix:
				# Try again if we don't have a fix yet.
				print("Waiting for fix...")
				lat, lon = 0, 0
			# We have a fix! (gps.has_fix is true)
			# Print out details about the fix like location, date, etc.
			lat = gps.latitude
			lon = gps.longitude
			if not arg_dict['test']:
				print("GPS: ",[lat,lon])
				send_data([lat, lon])

			print("Latitude: {0:.6f} degrees".format(lat))
			print("Longitude: {0:.6f} degrees".format(lon))
			print("Fix quality: {}".format(gps.fix_quality))
							
		sys.stdout.flush()
