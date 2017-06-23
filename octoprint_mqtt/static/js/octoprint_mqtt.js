$(function() {
    function MQTTViewModel(parameters) {
        
        var self = this;

        self.global_settings = parameters[0];
        
        self.availableProtocols = ko.observableArray(['MQTTv31','MQTTv311']);
      
        self.onBeforeBinding = function () {
            self.settings = self.global_settings.settings.plugins.octoprint_mqtt;
        };
    }

    ADDITIONAL_VIEWMODELS.push([
        MQTTViewModel,
        ["settingsViewModel"],
        ["#settings_plugin_mqtt"]
    ]);
});