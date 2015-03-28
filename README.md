# OctoPrint MQTT Plugin

This is an OctoPrint Plugin that adds support for [MQTT](http://mqtt.org/) to OctoPrint.

Out of the box OctoPrint will send all [event](http://docs.octoprint.org/en/devel/events/index.html#available-events)
including their payloads to the topic `octoprint/event/<event>`, where `<event>` is the corresponding event. The message
payload will be a JSON representation of the event's payload, with an additional property `_event` containing the name
of the event.

Examples:

| Topic                        | Message                                                          |
|------------------------------|------------------------------------------------------------------|
| octoprint/event/ClientOpened | `{"_event": "ClientOpened", "remoteAddress": "127.0.0.1"}`       |
| octoprint/event/Connected    | `{"baudrate": 250000, "_event": "Connected", "port": "VIRTUAL"}` |
| octoprint/event/PrintStarted | `{"origin": "local", "_event": "PrintStarted", "file":"/home/pi/.octoprint/uploads/case_bp_3.6.v1.0.gco", "filename": "case_bp_3.6.v1.0.gco"}` |

The plugin however also offers several helpers that allow other plugins to both publish as well as subscribe to
MQTT topics, see below.

## Installation

Install the plugin like you would install any regular Python package from source:

    pip install https://github.com/OctoPrint/OctoPrint-MQTT/archive/master.zip

Make sure you use the same Python environment that you installed OctoPrint under, otherwise the plugin
won't be able to satisfy its dependencies.

Restart OctoPrint. `octoprint.log` should show you that the plugin was successfully found and loaded.

## Configuration

The plugin currently offers no settings dialog, configuration needs to be done by manually editing `config.yaml`. The
following options are available:

``` yaml
plugins:
    mqtt:
        broker:
            # the broker's url, mandatory, if not configured the plugin will do nothing
            url: 127.0.0.1

            # the broker's port
            port: 1883

            # the username to use to connect with the broker, if not set no user
            # credentials will be sent
            #username: unset

            # the password to use to connect with the broker, only used if a
            # username is supplied too
            #password: unset

            # the keepalive value for the broker connection
            #keepalive: 60

        publish:
            # base topic under which to publish OctoPrint's messages
            baseTopic: octoprint/

            # topic for events, appended to the base topic, '{event}' will
            # be substituted with the event name
            eventTopic: event/{event}
```

## Helpers

### mqtt_publish(topic, payload, retained=False, qos=0, allow_queueing=False)

Publishes `payload` to `topic`. If `retained` is set to `True`, message will be flagged to be retained by the
broker. The QOS setting can be override with the `qos` parameter.

If the MQTT plugin is currently not connected to the broker but `allow_queueing` is `True`, the message will be
stored internally and published upon connection to the broker.

Returns `True` if the message was accepted to be published by the MQTT plugin, `False` if the message could not
be accepted (e.g. due to the plugin being not connected to the broker and queueing not being allowed).

### mqtt_subscribe(topic, callback, args=None, kwargs=None)

Subscribes `callback` for messages published on `topic`. The MQTT plugin will call the `callback` for received
messages like this:

    callback(topic, payload, args..., retained=..., qos=..., kwargs...)

`topic` will be the exact topic the message was received for, payload the message's payload, `retained` whether the
message was retained by the broker and `qos` the message's QOS setting.

The callback should therefore at least accept `topic` and `payload` of the message as positional arguments and
`retain` and `qos` as keyword arguments. If additional positional arguments or keyword arguments where provided
during subscription, they will be provided as outlined above.

### mqtt_unsubscribe(callback, topic=None)

Unsubscribes the `callback`. If not `topic` is provided all subscriptions for the `callback` will be removed, otherwise
only those matching the `topic` exactly.

### Example

The following single file plugin demonstrates how to use the provided helpers. Place it as `mqtt_test.py` into your
`~/.octoprint/plugins` (or equivalent) folder.

```python
import octoprint.plugin

class MqttTestPlugin(octoprint.plugin.StartupPlugin):

	def __init__(self):
		self.mqtt_publish = lambda *args, **kwargs: None
		self.mqtt_subscribe = lambda *args, **kwargs: None
		self.mqtt_unsubscribe = lambda *args, **kwargs: None

	def on_after_startup(self):
		helpers = self._plugin_manager.get_helpers("mqtt", "mqtt_publish", "mqtt_subscribe", "mqtt_unsubscribe")
		if helpers:
			if "mqtt_publish" in helpers:
				self.mqtt_publish = helpers["mqtt_publish"]
			if "mqtt_subscribe" in helpers:
				self.mqtt_subscribe = helpers["mqtt_subscribe"]
			if "mqtt_unsubscribe" in helpers:
				self.mqtt_unsubscribe = helpers["mqtt_unsubscribe"]

		self.mqtt_publish("octoprint/plugin/mqtt_test/pub", "test plugin startup")
		self.mqtt_subscribe("octoprint/plugin/mqtt_test/sub", self._on_mqtt_subscription)

	def _on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
		self._logger.info("Yay, received a message for {topic}: {message}".format(**locals()))
		self.mqtt_publish("octoprint/plugin/mqtt_test/pub", "echo: " + message)


__plugin_implementations__ = [MqttTestPlugin()]
```

## Acknowledgements & Licensing

OctoPrint-MQTT is licensed under the terms of the [APGLv3](https://gnu.org/licenses/agpl.html) (also included).

OctoPrint-MQTT uses the [Eclipse Paho Python Client](https://www.eclipse.org/paho/clients/python/) under the hood,
which is dual-licensed and used here under the terms of the [EDL v1.0 (BSD)](https://www.eclipse.org/org/documents/edl-v10.php).