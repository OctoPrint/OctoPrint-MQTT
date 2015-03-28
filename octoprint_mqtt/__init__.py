# coding=utf-8
from __future__ import absolute_import

import time
from collections import deque

import octoprint.plugin

class MqttPlugin(octoprint.plugin.SettingsPlugin,
                 octoprint.plugin.StartupPlugin,
                 octoprint.plugin.ShutdownPlugin,
                 octoprint.plugin.EventHandlerPlugin):

	def __init__(self):
		self._mqtt = None
		self._mqtt_connected = False

		self._mqtt_subscriptions = []

		self._mqtt_publish_queue = deque()
		self._mqtt_subscribe_queue = deque()

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
				keepalive=60
			),
			publish=dict(
				baseTopic="octoprint/",
				eventTopic="event/{event}",
			)
		)

	##~~ EventHandlerPlugin API

	def on_event(self, event, payload):
		topic = self._get_topic("event")

		if topic:
			import json
			data = dict(payload)
			data["_event"] = event
			self.mqtt_publish(topic.format(event=event), json.dumps(data))

	##~~ helpers

	def mqtt_connect(self):
		# TODO TLS, LWT, protocol

		broker_url = self._settings.get(["broker", "url"])
		broker_port = self._settings.get_int(["broker", "port"])
		broker_username = self._settings.get(["broker", "username"])
		broker_password = self._settings.get(["broker", "password"])
		broker_keepalive = self._settings.get_int(["broker", "keepalive"])

		import paho.mqtt.client as mqtt

		if self._mqtt is None:
			self._mqtt = mqtt.Client()

		if broker_username is not None:
			self._mqtt.username_pw_set(broker_username, password=broker_password)

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
		self._mqtt.subscribe(subbed_topics)

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
				callback(*args, **kwargs)

	def _get_topic(self, topic_type):
		sub_topic = self._settings.get(["publish", topic_type + "Topic"])
		if not sub_topic:
			return None

		return self._settings.get(["publish", "baseTopic"]) + sub_topic

__plugin_name__ = "mqtt"

def __plugin_init__():
	plugin = MqttPlugin()

	global __plugin_helpers__
	__plugin_helpers__ = dict(
		mqtt_publish=plugin.mqtt_publish,
		mqtt_subscribe=plugin.mqtt_subscribe,
		mqtt_unsubscribe=plugin.mqtt_unsubscribe
	)

	global __plugin_implementations__
	__plugin_implementations__ = [plugin]
