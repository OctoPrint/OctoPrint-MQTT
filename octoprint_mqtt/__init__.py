# coding=utf-8
from __future__ import absolute_import

import json
import time
from collections import deque

import octoprint.plugin

class MqttPlugin(octoprint.plugin.SettingsPlugin,
                 octoprint.plugin.StartupPlugin,
                 octoprint.plugin.ShutdownPlugin,
                 octoprint.plugin.EventHandlerPlugin,
                 octoprint.plugin.ProgressPlugin,
                 octoprint.plugin.TemplatePlugin,
                 octoprint.plugin.AssetPlugin,
                 octoprint.printer.PrinterCallback):

	def __init__(self):
		self._mqtt = None
		self._mqtt_connected = False

		self._mqtt_subscriptions = []

		self._mqtt_publish_queue = deque()
		self._mqtt_subscribe_queue = deque()

		self.lastTemp = {}



	def initialize(self):
		self._printer.register_callback(self)

		if self._settings.get(["broker", "url"]) is None:
			self._logger.error("No broker URL defined, MQTT plugin won't be able to work")
			return False

	##~~ TemplatePlugin API

	def get_template_configs(self):
		return [
			dict(type="settings", name="MQTT")
		]

	##~~ AssetPlugin API

	def get_assets(self):
		return dict(js=["js/mqtt.js"])

	##~~ StartupPlugin API

	def on_startup(self, host, port):
		self.mqtt_connect()

	##~~ ShutdownPlugin API

	def on_shutdown(self):
		self.mqtt_disconnect(force=True)

	##~~ SettingsPlugin API

	def get_settings_defaults(self):
		return dict(
			broker=dict(
				url=None,
				port=1883,
				username=None,
				password=None,
				keepalive=60,
				tls=dict(),
				tls_insecure=False,
				protocol="MQTTv31"
			),
			publish=dict(
				baseTopic="octoprint/",
				eventTopic="event/{event}",
				eventActive=True,
				eventServerActive=True,
				eventPrintCommActive=True,
				eventFileHandlActive=True,
				eventPrintingActive=True,
				eventGCodePrcActive=True,
				eventTimelapsesActive=True,
				eventSlicingActive=True,
				eventSettingsActive=True,
				progressTopic="progress/{progress}",
				progressActive=True,
				temperatureTopic="temperature/{temp}",
				temperatureActive=True,
				temperatureThreshold=0.1
			)
		)

	##~~ EventHandlerPlugin API

	def on_event(self, event, payload):
		topic = self._get_topic("event")

		if topic:
			if self._is_active(event):
				if payload is None:
					data = dict()
				else:
					data = dict(payload)
				data["_event"] = event
				self.mqtt_publish(topic.format(event=event), json.dumps(data))

	##~~ ProgressPlugin API

	def on_print_progress(self, storage, path, progress):
		topic = self._get_topic("progress")

		if topic:
			data = dict(location=storage,
			            path=path,
			            progress=progress)
			self.mqtt_publish(topic.format(progress="printing"), json.dumps(data), retained=True)

	def on_slicing_progress(self, slicer, source_location, source_path, destination_location, destination_path, progress):
		topic = self._get_topic("progress")

		if topic:
			data = dict(slicer=slicer,
			            source_location=source_location,
			            source_path=source_path,
			            destination_location=destination_location,
			            destination_path=destination_path,
			            progress=progress)
			self.mqtt_publish(topic.format(progress="slicing"), json.dumps(data), retained=True)

	##~~ PrinterCallback

	def on_printer_add_temperature(self, data):
		topic = self._get_topic("temperature")
		threshold = self._settings.getFloat(["publish", "temperatureThreshold"])

		if topic:
			for key, value in data.items():
				if key == "time":
					continue

				if key not in self.lastTemp \
						or abs(value["actual"] - self.lastTemp[key]["actual"]) >= threshold \
						or value["target"] != self.lastTemp[key]["target"]:
					# unknown key, new actual or new target -> update mqtt topic!
					dataset = dict(actual=value["actual"],
					               target=value["target"])
					self.mqtt_publish(topic.format(temp=key), json.dumps(dataset), retained=True, allow_queueing=True)
					self.lastTemp.update({key:data[key]})

	##~~ Softwareupdate hook

	def get_update_information(self):
		return dict(
			mqtt=dict(
				displayName=self._plugin_name,
				displayVersion=self._plugin_version,

				# version check: github repository
				type="github_release",
				user="OctoPrint",
				repo="OctoPrint-MQTT",
				current=self._plugin_version,

				# update method: pip
				pip="https://github.com/OctoPrint/OctoPrint-MQTT/archive/{target_version}.zip"
			)
		)

	##~~ helpers

	def mqtt_connect(self):
		# TODO LWT

		broker_url = self._settings.get(["broker", "url"])
		broker_port = self._settings.get_int(["broker", "port"])
		broker_username = self._settings.get(["broker", "username"])
		broker_password = self._settings.get(["broker", "password"])
		broker_keepalive = self._settings.get_int(["broker", "keepalive"])
		broker_tls = self._settings.get(["broker", "tls"], asdict=True)
		broker_tls_insecure = self._settings.get_boolean(["broker", "tls_insecure"])
		broker_protocol = self._settings.get(["broker", "protocol"])

		if broker_url is None:
			return

		import paho.mqtt.client as mqtt

		protocol_map = dict(MQTTv31=mqtt.MQTTv31,
		                    MQTTv311=mqtt.MQTTv311)
		if broker_protocol in protocol_map:
			protocol = protocol_map[broker_protocol]
		else:
			protocol = mqtt.MQTTv31

		if self._mqtt is None:
			self._mqtt = mqtt.Client(protocol=protocol)

		if broker_username is not None:
			self._mqtt.username_pw_set(broker_username, password=broker_password)

		tls_active = False
		if broker_tls:
			tls_args = dict((key, value) for key, value in broker_tls.items() if value)
			ca_certs = tls_args.pop("ca_certs", None)
			if ca_certs: # cacerts must not be None for tls_set to work
				self._mqtt.tls_set(ca_certs, **tls_args)
				tls_active = True

		if broker_tls_insecure and tls_active:
			self._mqtt.tls_insecure_set(broker_tls_insecure)

		self._mqtt.on_connect = self._on_mqtt_connect
		self._mqtt.on_disconnect = self._on_mqtt_disconnect
		self._mqtt.on_message = self._on_mqtt_message

		self._mqtt.connect_async(broker_url, broker_port, keepalive=broker_keepalive)
		self._mqtt.loop_start()

	def mqtt_disconnect(self, force=False):
		if self._mqtt is None:
			return

		self._mqtt.loop_stop()

		if force:
			time.sleep(1)
			self._mqtt.loop_stop(force=True)

	def mqtt_publish(self, topic, payload, retained=False, qos=0, allow_queueing=False):
		if not self._mqtt_connected:
			if allow_queueing:
				self._logger.debug("Not connected, enqueing message: {topic} - {payload}".format(**locals()))
				self._mqtt_publish_queue.append((topic, payload, retained, qos))
				return True
			else:
				return False

		self._mqtt.publish(topic, payload=payload, retain=retained, qos=qos)
		self._logger.debug("Sent message: {topic} - {payload}".format(**locals()))
		return True

	def mqtt_subscribe(self, topic, callback, args=None, kwargs=None):
		if args is None:
			args = []
		if kwargs is None:
			kwargs = dict()

		self._mqtt_subscriptions.append((topic, callback, args, kwargs))

		if not self._mqtt_connected:
			self._mqtt_subscribe_queue.append(topic)
		else:
			self._mqtt.subscribe(topic)

	def mqtt_unsubscribe(self, callback, topic=None):
		subbed_topics = [subbed_topic for subbed_topic, subbed_callback, _, _ in self._mqtt_subscriptions if callback == subbed_callback and (topic is None or topic == subbed_topic)]

		def remove_sub(entry):
			subbed_topic, subbed_callback, _, _ = entry
			return not (callback == subbed_callback and (topic is None or subbed_topic == topic))

		self._mqtt_subscriptions = filter(remove_sub, self._mqtt_subscriptions)

		if self._mqtt_connected and subbed_topics:
			self._mqtt.unsubscribe(*subbed_topics)

	##~~ mqtt client callbacks

	def _on_mqtt_connect(self, client, userdata, flags, rc):
		if not client == self._mqtt:
			return

		if not rc == 0:
			reasons = [
				None,
				"Connection to mqtt broker refused, wrong protocol version",
				"Connection to mqtt broker refused, incorrect client identifier",
				"Connection to mqtt broker refused, server unavailable",
				"Connection to mqtt broker refused, bad username or password",
				"Connection to mqtt broker refused, not authorised"
			]

			if rc < len(reasons):
				reason = reasons[rc]
			else:
				reason = None

			self._logger.error(reason if reason else "Connection to mqtt broker refused, unknown error")
			return

		self._logger.info("Connected to mqtt broker")

		if self._mqtt_publish_queue:
			try:
				while True:
					topic, payload, retained, qos = self._mqtt_publish_queue.popleft()
					self._mqtt.publish(topic, payload=payload, retain=retained, qos=qos)
			except IndexError:
				# that's ok, queue is just empty
				pass

		subbed_topics = list(map(lambda t: (t, 0), {topic for topic, _, _, _ in self._mqtt_subscriptions}))
		if subbed_topics:
			self._mqtt.subscribe(subbed_topics)
			self._logger.debug("Subscribed to topics")

		self._mqtt_connected = True

	def _on_mqtt_disconnect(self, client, userdata, rc):
		if not client == self._mqtt:
			return

		if not rc == 0:
			self._logger.error("Disconnected from mqtt broker for unknown reasons")

		self._mqtt_connected = False

	def _on_mqtt_message(self, client, userdata, msg):
		if not client == self._mqtt:
			return

		from paho.mqtt.client import topic_matches_sub
		for subscription in self._mqtt_subscriptions:
			topic, callback, args, kwargs = subscription
			if topic_matches_sub(topic, msg.topic):
				args = [msg.topic, msg.payload] + args
				kwargs.update(dict(retained=msg.retain, qos=msg.qos))
				try:
					callback(*args, **kwargs)
				except:
					self._logger.exception("Error while calling mqtt callback")

	def _get_topic(self, topic_type):
		sub_topic = self._settings.get(["publish", topic_type + "Topic"])
		topic_active = self._settings.get(["publish", topic_type + "Active"])
		if not sub_topic or not topic_active:
			return None

		return self._settings.get(["publish", "baseTopic"]) + sub_topic

	def _is_active(self, event):
		if event in ["Startup", "Shutdown","ClientOpened","ClientClosed","ConnectivityChanged"]:
			return self._settings.get_boolean(["publish", "eventServerActive"])
		if event in ["Connecting","Connected","Disconnecting","Disconnected","Error","PrinterStateChanged"]:
			return self._settings.get_boolean(["publish", "eventPrintCommActive"])
		if event in ["Upload","FileAdded","FileRemoved","FolderAdded","FolderRemoved","UpdatedFiles","MetadataAnalysisStarted","MetadataAnalysisFinished","FileSelected","FileDeselected","TransferStarted","TransferDone"]:
			return self._settings.get_boolean(["publish", "eventFileHandlActive"])
		if event in ["PrintStarted","PrintFailed","PrintDone","PrintCancelled","PrintPaused","PrintResumed"]:
			return self._settings.get_boolean(["publish", "eventPrintingActive"])
		if event in ["PowerOn","PowerOff","Home","ZChange","Dwell","Waiting","Cooling","Alert","Conveyor","Eject","EStop","PositionUpdate","ToolChange"]:
			return self._settings.get_boolean(["publish", "eventGCodePrcActive"])
		if event in ["CaptureStart","CaptureDone","CaptureFailed","MovieRendering","MovieDone","MovieFailed"]:
			return self._settings.get_boolean(["publish", "eventTimelapsesActive"])
		if event in ["SlicingStarted","SlicingDone","SlicingCancelled","SlicingFailed","SlicingProfileAdded","SlicingProfileModified","SlicingProfileDeleted"]:
			return self._settings.get_boolean(["publish", "eventSlicingActive"])
		if event == "SettingsUpdated":
			return self._settings.get_boolean(["publish", "eventSettingsActive"])
		return False



__plugin_name__ = "MQTT"

def __plugin_load__():
	plugin = MqttPlugin()

	global __plugin_helpers__
	__plugin_helpers__ = dict(
		mqtt_publish=plugin.mqtt_publish,
		mqtt_subscribe=plugin.mqtt_subscribe,
		mqtt_unsubscribe=plugin.mqtt_unsubscribe
	)

	global __plugin_implementation__
	__plugin_implementation__ = plugin

	global __plugin_hooks__
	__plugin_hooks__ = {
		"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
	}
