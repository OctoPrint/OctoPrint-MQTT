# OctoPrint MQTT Plugin

This is an OctoPrint Plugin that adds support for [MQTT](http://mqtt.org/) to OctoPrint.

Out of the box OctoPrint will send all [events](http://docs.octoprint.org/en/devel/events/index.html#available-events)
including their payloads to the topic `octoPrint/event/<event>`, where `<event>` will be the name of the event. The message
payload will be a JSON representation of the event's payload, with an additional property `_event` containing the name
of the event and a property `_timestamp` containing the unix timestamp of when the message was created.

Examples:

| Topic                        | Message                                                          |
|------------------------------|------------------------------------------------------------------|
| octoPrint/event/ClientOpened | `{"_timestamp": 1517190629, "_event": "ClientOpened", "remoteAddress": "127.0.0.1"}`       |
| octoPrint/event/Connected    | `{"_timestamp": 1517190629, "_event": "Connected", "baudrate": 250000, "port": "VIRTUAL"}` |
| octoPrint/event/PrintStarted | `{"_timestamp": 1517190629, "_event": "PrintStarted", "origin": "local", "file":"/home/pi/.octoprint/uploads/case_bp_3.6.v1.0.gco", "filename": "case_bp_3.6.v1.0.gco"}` |

The print progress and the slicing progress will also be send to the topic `octoPrint/progress/printing` and
`octoPrint/progress/slicing` respectively. The payload will contain the `progress` as an integer between 0 and 100.
Print progress will also contain information about the currently printed file (storage `location` and `path` on storage),
slicing progress will contain information about the currently sliced file (storage `source_location` and `destination_location`,
`source_path` and `destination_path` on storage, used `slicer`). The payload will also contain a property `_timestamp`
containing the unix timestamp of when the message was created. The published progress messages will be marked as
retained.

Examples:

| Topic                        | Message                                                          |
|------------------------------|------------------------------------------------------------------|
| octoPrint/progress/printing  | `{"_timestamp": 1517190629, "progress": 23, "location": "local", "path": "test.gco"}`      |
| octoPrint/progress/slicing   | `{"_timestamp": 1517190629, "progress": 42, "source_location": "local", "source_path": "test.stl", "destination_location": "local", "destination_path": "test.gcode", "slicer": "cura"}` |

The plugin also publishes the temperatures of the tools and the bed to `octoPrint/temperature/<tool>` where `<tool>` will either
be 'bed' or 'toolX' (X is the number of the tool). The payload will contain the `actual` and the `target` temperature as floating point value plus the current `time` as unix timestamp in seconds.
New messages will not be published constantly, but only when a value changes. The payload will also contain a property `_timestamp`
containing the unix timestamp of when the message was created. The published messages will be marked as retained.

Examples:

| Topic                        | Message                                                          |
|------------------------------|------------------------------------------------------------------|
| octoPrint/temperature/tool0  | `{"_timestamp": 1517190629, "actual": 65.3, "target": 210.0}`                              |
| octoPrint/temperature/bed    | `{"_timestamp": 1517190629, "actual": 42.1, "target": 65.0}`                               |

Additionally the plugin will publish `connected` to `octoPrint/mqtt` on connection and instruct the MQTT broker to publish
`disconnected` there if the connection gets closed. The published messages will be marked as retained.

Examples:

| Topic                        | Message              |
|------------------------------|----------------------|
| octoPrint/mqtt               | `connected`          |

You are able to deactivate topics and the status/last will in the settings. This allows you to e.g. only send temperature messages when you don't
need event or progress messages.

If the Printer Data option is set, then extended printer information as outlined in the
[Common data model](http://docs.octoprint.org/en/master/api/datamodel.html) will be included in a `printer_data` attribute.
Useful to get information such as print time remaining.

Example:

| Topic                        | Message              |
|------------------------------|----------------------|
| octoPrint/progress/printing  | `{"progress": 0, "_timestamp": 1525654824, "location": "local", "path": "Stringing_Test.gco", "printer_data": {"progress": {"completion": 0.008520926537352922, "printTimeLeftOrigin": "average", "printTime": 0, "printTimeLeft": 273, "filepos": 139}, "state": {"text": "Printing", "flags": {"cancelling": false, "paused": false, "operational": true, "pausing": false, "printing": true, "sdReady": true, "error": false, "ready": false, "closedOrError": false}}, "currentZ": null, "job": {"file": {"origin": "local", "name": "Stringing_Test.gco", "date": 1525586467, "path": "Stringing_Test.gco", "display": "Stringing_Test.gco", "size": 1631278}, "estimatedPrintTime": 1242.9603101308749, "averagePrintTime": 273.6990565955639, "filament": {"tool0": {"volume": 0.0, "length": 363.0717599999999}}, "lastPrintTime": 269.25606203079224}, "offsets": {}}}` |

The plugin also offers several helpers that allow other plugins to both publish as well as subscribe to
MQTT topics, see below for details and a usage example.

## Installation

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager) using this URL:

    https://github.com/OctoPrint/OctoPrint-MQTT/archive/master.zip

## Configuration

The plugin offers a settings dialog that allows you to configure all relevant settings. If you want to configure things
manually by editing `config.yaml`, this is the structure you'd find therein:

``` yaml
plugins:
    mqtt:
        broker:
            # the broker's url, mandatory, if not configured the plugin will do nothing
            url: 127.0.0.1

            # the broker's port
            #port: 1883

            # the username to use to connect with the broker, if not set no user
            # credentials will be sent
            #username: unset

            # the password to use to connect with the broker, only used if a
            # username is supplied too
            #password: unset

            # the keepalive value for the broker connection
            #keepalive: 60

            # tls settings
            #tls:
                # path to the server's certificate file
                #ca_certs: unset

                # paths to the PEM encoded client certificate and private keys
                # respectively, must not be password protected, only necessary
                # if broker requires client certificate authentication
                #certfile: unset
                #keyfile: unset

                # a string specifying which encryption ciphers are allowable for this connection
                #ciphers: unset

            # configure verification of the server hostname in the server certificate.
            #tls_insecure: false

            # configure protocol version to use, valid values: MQTTv31 and MQTTv311
            #protocol: MQTTv31

        publish:
            # base topic under which to publish OctoPrint's messages
            #baseTopic: octoPrint/

            # include extended printer data in a printer_data attribute, this will
            # greatly increase the size of each message
            # printerData: false

            # topic for events, appended to the base topic, '{event}' will
            # be substituted with the event name
            #eventTopic: event/{event}

            # should events be published?
            #eventActive: true

            # topic for print and slicer progress, appended to the base topic,
            # '{progress}' will be substituted with either 'printing' or 'slicing'
            #progressTopic: progress/{progress}

            # should progress be published?
            #progressActive: true

            # topic for temperatures, appended to the base topic,
            # '{temp}' will be substituted with either 'toolX' (X is the number of the tool) or 'bed'
            #temperatureTopic: temperature/{temp}

            # should temperatures be published?
            #temperatureActive: true

            # should mqtt connection status / last will be published?
            #lwActive: true

            # topic for connection status / last will
            #lwTopic: mqtt
```

## Helpers

### mqtt_publish(topic, payload, retained=False, qos=0, allow_queueing=False, raw_data=False)

Publishes `payload` to `topic`. If `retained` is set to `True`, message will be flagged to be retained by the
broker. The QOS setting can be overridden with the `qos` parameter.

`payload` may be a string in which case it will be sent as is. Otherwise a value conversion to JSON will be performed, unless you set `raw_data` to `True`.

If the MQTT plugin is currently not connected to the broker but `allow_queueing` is `True`, the message will be
stored internally and published upon connection to the broker.

Returns `True` if the message was accepted to be published by the MQTT plugin, `False` if the message could not
be accepted (e.g. due to the plugin being not connected to the broker and queueing not being allowed).

### mqtt_publish_with_timestamp(topic, payload, retained=False, qos=0, allow_queueing=False, timestamp=None)

Publishes `payload` to `topic` including a timestamp. `payload` *must* be a Python `dict` and will be extended by a
property `_timestamp` set to the provided `timestamp` or - if unset - the current timestamp.

If the `publish.printerData` option is set, then all of the data from `self._printer.get_current_data()` will be
included as a `printer_data` attribute in the payload. Useful to get things such as time remaining.

Everything else behaves as `mqtt_publish` (which is also used internally).

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

		self.mqtt_publish("octoPrint/plugin/mqtt_test/pub", "test plugin startup")
		self.mqtt_subscribe("octoPrint/plugin/mqtt_test/sub", self._on_mqtt_subscription)

	def _on_mqtt_subscription(self, topic, message, retained=None, qos=None, *args, **kwargs):
		self._logger.info("Yay, received a message for {topic}: {message}".format(**locals()))
		self.mqtt_publish("octoPrint/plugin/mqtt_test/pub", "echo: " + message)


__plugin_implementations__ = [MqttTestPlugin()]
```

## Acknowledgements & Licensing

OctoPrint-MQTT is licensed under the terms of the [APGLv3](https://gnu.org/licenses/agpl.html) (also included).

OctoPrint-MQTT uses the [Eclipse Paho Python Client](https://www.eclipse.org/paho/clients/python/) under the hood,
which is dual-licensed and used here under the terms of the [EDL v1.0 (BSD)](https://www.eclipse.org/org/documents/edl-v10.php).
