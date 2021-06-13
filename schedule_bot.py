#!/usr/bin/env python

import os
import pickle
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import telegram
# import sched, time
from datetime import datetime, timedelta
import threading
import pickle
import pathlib

# import logging
#
#
# logging_fmt = '[%(asctime)s] %(filename)s [%(levelname)s] %(message)s'
# logging.basicConfig(filename='security.log', filemode='w', format=logging_fmt, level=logging.INFO)
#


class schedule_bot() :

	def __init__(self, token) :
		#initialize bot
		updater = Updater(token, use_context=True)
		dp = updater.dispatcher
		self.bot=telegram.Bot(token=token)



		#load data
		self.data_path=str(pathlib.Path(__file__).parent.absolute())+"/scheduledb.p"
		try :
			with open(self.data_path, 'rb') as handle:
				self.schedules= pickle.load(handle)
				for id in self.schedules.keys() :
					self.add_interupts(id)

		except:
			self.schedules={}


		#register listeners
		dp.add_handler(CommandHandler("arrivaltime", self.set_arrival)) #arrival time
		dp.add_handler(CommandHandler("arrival", self.set_arrival)) #arrival time
		dp.add_handler(CommandHandler("alerts", self.set_alerts)) #list of alert times to be notified at.
		dp.add_handler(CommandHandler("sleeptime", self.set_sleep_time)) #sleep time
		dp.add_handler(CommandHandler("sleep", self.set_sleep_time)) #sleep time
		dp.add_handler(CommandHandler("info", self.send_info)) #info
		dp.add_handler(CommandHandler("datadump", self.datadump)) #info

		dp.add_handler(CommandHandler("help", self.help))


		print("starting polling")
		updater.start_polling()

	#backs up data for persistance
	def save_data(self) :
		print("saving")
		to_save=self.schedules.copy()
		for info in to_save.values() :
			info["interupts"]=[]
		with open(self.data_path, 'wb') as handle:
			print(pickle.dump(self.schedules, handle))
		print("saved")



	#schedules a message, returns timer for cancelling
	def schedule_message(self,id, seconds_until_interupt,message) :

		print("scheduling message \"{}\" for ".format(message), seconds_until_interupt)
		timer=threading.Timer(seconds_until_interupt, self.send_message, args=[id,message])
		timer.start()
		return timer

	#Schedules removal of the code for this particular alarm
	def schedule_cleanup(self,id, seconds_until_interupt) :
		timer=threading.Timer(seconds_until_interupt, self.cleanup_interupt, args=[id])
		timer.start()
		return timer

	#the function to call which cleans up after everythign is done
	def cleanup_interupt(self,id) :
		self.schedules[id]["arrival_time"]=[] #clear arrival time
		self.schedules[id]["interupts"]=[]
		self.send_message(id, "cleanup")

	#returns the number of seconds that the sleep delay takes up
	def get_sleep_time(self,id) :
		sleep_time=self.schedules[id]["sleep_time"]
		if len(sleep_time)==0 :
			return 0
		#gets the alarm time of the ID and subtracts the delay
		return (sleep_time[0]*60+sleep_time[1])*60 #nhn in seconds

	#returns the number of seconds until a time, in 24 hour format
	def seconds_until_time(self, hour, minute) :
		now = datetime.now()
		diff=(timedelta(hours=24) - (now - now.replace(hour=hour, minute=minute, second=0, microsecond=0))).total_seconds() % (24 * 3600)
		return diff

	#populates a new schedule
	def populate_schedule_dict(self,id) :
		#includes default alert times
		info_dict={"arrival_time":[], "alerts":[45,30,15],"interupts":[],"sleep_time":[]}
		print("populated new data")
		self.schedules[id]=info_dict

	#adds arrivals to the structure
	def add_arrival(self, id, arrival_text) :
		time_list=[int(t) for t in arrival_text.split(":")]

		print("time_list:",time_list)
		#checks if id/person already has an entry

		if id not in self.schedules.keys() :
			self.populate_schedule_dict(id)
		self.schedules[id]["arrival_time"]=time_list
		print("added arrival time ", self.schedules[id])

		self.save_data()
		self.add_interupts(id)

	#adds alerts to the structure
	def add_alerts(self, id, alert_text) :
		#add alerts to user id
		alert_list=[int(t) for t in alert_text.split(",")]
		if id not in self.schedules.keys() :
			self.populate_schedule_dict(id)
		self.schedules[id]["alerts"]=alert_list

		self.add_interupts(id)
		self.save_data()

	#adds the amount of time for sleep to the structure
	def add_sleep_time(self, id, sleep_time_text) :
		time_list=[int(t) for t in sleep_time_text.split(":")]
		if id not in self.schedules.keys() :
			self.populate_schedule_dict(id)
		self.schedules[id]["sleep_time"]=time_list

		self.add_interupts(id)
		self.save_data()


	#adds interupts for all the alerts
	def add_interupts(self, id) :
		print("adding interupts")
		#removes old interupts if they exist
		for timer in self.schedules[id]["interupts"] :
			timer.cancel()
		#adds new interupts for each time alert time
		arrival_time=self.schedules[id]["arrival_time"]
		time_until_arrival=self.seconds_until_time(arrival_time[0],arrival_time[1])
		print("minutes until arrival", time_until_arrival/60)
		time_until_sleep=time_until_arrival-self.get_sleep_time(id)
		print("minutes until sleep", time_until_sleep/60)


		for alert in self.schedules[id]["alerts"] :
			seconds=time_until_sleep-alert*60
			message="this is your {} minute alert. Your arrival time is {}:{}.".format(alert, str(arrival_time[0]).zfill(2),str(arrival_time[1]).zfill(2))
			message_interupt=self.schedule_message(id, seconds, message)
			self.schedules[id]["interupts"].append(message_interupt)

		message="Goodnight!"
		message_interupt=self.schedule_message(id, time_until_sleep, message)
		self.schedules[id]["interupts"].append(message_interupt)

		#adds an interupt which removes the alarm after time 0
		cleanup_interupt=self.schedule_cleanup(id, time_until_sleep+1)
		self.schedules[id]["interupts"].append(cleanup_interupt)

		# print(self.schedules[id])

	#generates pretty text descrining the status of the user
	def get_status_message(self, id) :
		m=""
		if id not in self.schedules.keys() :
			m="You currently have no data setup"
		else :
			info=self.schedules[id]


			#alert times
			m+="Your alert intervals are set at"
			for alert in info["alerts"] :
				m+=" {},".format(alert)
			m=m[:-1] #remove last ,
			m+=" minutes\n"

			#arrival time dependant values
			if(len(info["arrival_time"])==0) :
				m+="You do not currently have a set arrival time\n"
			else :
				m+="Your arrival time is {}:{}\n".format(str(info["arrival_time"][0]).zfill(2),str(info["arrival_time"][1]).zfill(2))
				arrival_time=info["arrival_time"]
				print(arrival_time)
				time_until_arrival=self.seconds_until_time(arrival_time[0],arrival_time[1])
				print(time_until_arrival)
				time_until_sleep=time_until_arrival-self.get_sleep_time(id)
				print(time_until_sleep)
				hours=(time_until_sleep/60)/60
				minutes=int(60*(hours%1)) #yes this is kinda clunky
				hours=int(hours)

				m+="There is {}:{} until you go to sleep\n".format(str(hours).zfill(2),str(minutes).zfill(2))


			#sleep time
			if(len(info["sleep_time"]))==0 :
				m+="You currently do not have any amount of time set for sleep.\n"
			else :
				m+="The amount of time you set for sleep is {}:{}\n".format(str(info["sleep_time"][0]).zfill(2),str(info["sleep_time"][1]).zfill(2))




		return m


	#Sets a new arrival time
	def set_arrival(self,update, context):
		received_text=update.message.text
		id=update.message.chat.id
		try:
			arrival_text=received_text.split(" ", 1)[1] #this should remove the command
			self.add_arrival(id, arrival_text)
			self.send_message(id, self.get_status_message(id))
		except:
			self.send_message(id,"Something went wrong, please try again")

	#Sets a new sleep time
	def set_sleep_time(self,update, context):
		received_text=update.message.text
		id=update.message.chat.id
		try:
			sleep_text=received_text.split(" ", 1)[1] #this should remove the command
			self.add_sleep_time(id, sleep_text)
			self.send_message(id, self.get_status_message(id))
		except:
			self.send_message(id,"Something went wrong, please try again")

	#Sends info
	def send_info(self,update, context):
		id=update.message.chat.id
		message=self.get_status_message(id)
		self.send_message(id, message)


	def datadump(self,update, context):
		id=update.message.chat.id
		self.send_message(id, str(self.schedules))


	#Sets a new series of alert times
	def set_alerts(self,update, context):
		id=update.message.chat.id
		try:
			received_text=update.message.text
			alert_text=received_text.split(" ", 1)[1] #this should remove the command
			self.add_alerts(id,alert_text)
			self.send_message(id, self.get_status_message(id))
		except:
			self.send_message(id,"Something went wrong, please try again")




	def help(self, update, context):
		help_message="/arrivaltime or /arrival is the time you want to arrive, formatted as \"hour:minute\". It is in 24 hour format.\n "
		help_message+="/sleeptime or /sleep the amount of time you sleep+commute+whatever for, formatted as \"hour:minute\"\n "
		help_message+="/alerts is a list of the number of minutes before sleep you want to be alerted, e.g \"45,30,15\"\n "
		help_message+="/info prints out your current information\n "
		update.message.reply_text(help_message)

	def send_message(self, id,message) :
		print("sending message ", message)
		self.bot.send_message(text=message, chat_id=id)




def main():
	TOKEN="1744090845:AAE22dX9YGxod3zJOV7MG_msNXgS9FP835s"
	# ID="-354289193"
	ts=schedule_bot(TOKEN)
	print("started telegram bot")


main()
