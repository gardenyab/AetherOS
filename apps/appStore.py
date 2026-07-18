import urllib
import json

class AppStore:
    """Apps manager"""
    
    requirements = []
    requirementsApt = []

    def __init__(self):
        self.appsListUrl = "https://raw.githubusercontent.com/gardenyab/AetherOSAppsRepo/refs/heads/main/apps.json" 
    
    def _getAppsList(self, url):
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode())
                self.data = data
        except Exception:
            self.data = {} 
    
    def show_apps(self):
        try:
            self._getAppsList(self.appsListUrl)
            text = []
            for i in self.data:
                text.append(f"•. {i} - {self.data['i']['version']}.\n    {self.data['i']['description']}")
            messageText = "\n".join(text)
            print(messageText)
        except Exception as e:
            print(str(e))
