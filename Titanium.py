import sublime
import sublime_plugin
import json
import subprocess


class TitaniumCommand(sublime_plugin.WindowCommand):

    def run(self, *args, **kwargs):
        settings = sublime.load_settings('Titanium.sublime-settings')
        self.cli              = settings.get("titaniumCLI", "/usr/local/bin/titanium")
        self.android          = settings.get("androidSDK", "/opt/android-sdk") + "/tools/android"
        self.loggingLevel     = settings.get("loggingLevel", "info")
        self.simulatorDisplay = str(settings.get("simulatorDisplay", "--retina"))
        self.simulatorHeight  = str(settings.get("simulatorHeight", "--tall"))
        self.iosVersion       = str(settings.get("iosVersion", "unknown"))

        folders = self.window.folders()
        if len(folders) <= 0:
            self.show_quick_panel(["ERROR: Must have a project open"], None)
        else:
            if len(folders) == 1:
                self.multipleFolders = False
                self.project_folder = folders[0]
                self.project_sdk = self.get_project_sdk_version()
                self.pick_platform()
            else:
                self.multipleFolders = True
                self.pick_project_folder(folders)

    def pick_project_folder(self, folders):
        folderNames = []
        for folder in folders:
            index = folder.rfind('/') + 1
            if index > 0:
                folderNames.append(folder[index:])
            else:
                folderNames.append(folder)

        # only show most recent when there is a command stored
        if 'titaniumMostRecent' in globals():
            folderNames.insert(0, 'most recent configuration')

        self.show_quick_panel(folderNames, self.select_project)

    def select_project(self, select):
        folders = self.window.folders()
        if select < 0:
            return

        # if most recent was an option, we need subtract 1
        # from the selected index to match the folders array
        # since the "most recent" option was inserted at the beginning
        if 'titaniumMostRecent' in globals():
            select = select - 1

        if select == -1:
            self.window.run_command("exec", {"cmd": titaniumMostRecent})
        else:
            self.project_folder = folders[select]
            self.project_sdk = self.get_project_sdk_version()
            self.pick_platform()


    def pick_platform(self):
        self.platforms = ["android", "ios", "mobileweb", "clean"]

        # only show most recent when there are NOT multiple top level folders
        # and there is a command stored
        if self.multipleFolders == False and 'titaniumMostRecent' in globals():
            self.platforms.insert(0, 'most recent configuration')

        self.show_quick_panel(self.platforms, self.select_platform)

    def select_platform(self, select):
        if select < 0:
            return
        self.platform = self.platforms[select]

        if self.platform == "most recent configuration":
            self.window.run_command("exec", {"cmd": titaniumMostRecent})
        elif self.platform == "ios":
            self.targets = ["simulator", "device", "dist-appstore", "dist-adhoc"]
            self.show_quick_panel(self.targets, self.select_ios_target)
        elif self.platform == "android":
            self.targets = ["emulator", "device", "dist-playstore"]
            self.show_quick_panel(self.targets, self.select_android_target)
        elif self.platform == "mobileweb":
            self.targets = ["development", "production"]
            self.show_quick_panel(self.targets, self.select_mobileweb_target)
        else:  # clean project
            self.window.run_command("exec", {"cmd": [self.cli, "clean", "--no-colors", "--project-dir", self.project_folder]})

    # Sublime Text 3 requires a short timeout between quick panels
    def show_quick_panel(self, options, done):
        sublime.set_timeout(lambda: self.window.show_quick_panel(options, done), 10)

    # get the current project's SDK from tiapp.xml
    def get_project_sdk_version(self):
        process = subprocess.Popen([self.cli, "project", "sdk-version", "--project-dir", self.project_folder, "--output=text"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        return result.decode('utf-8').rstrip('\n')

    def run_titanium(self, options=[]):
        cmd = [self.cli, "build", "--sdk", self.project_sdk, "--project-dir", self.project_folder, "--no-colors", "--platform", self.platform, "--log-level", self.loggingLevel]
        if (self.iosVersion is not "unknown" and self.iosVersion is not ""):
            options.extend(["--ios-version", self.iosVersion])
        cmd.extend(options)

        # save most recent command
        global titaniumMostRecent
        titaniumMostRecent = cmd

        self.window.run_command("exec", {"cmd": cmd})

    #--------------------------------------------------------------
    # MOBILE WEB
    #--------------------------------------------------------------

    def select_mobileweb_target(self, select):
        if select < 0:
            return
        self.run_titanium(["--deploy-type", self.targets[select]])

    #--------------------------------------------------------------
    # ANDROID
    #--------------------------------------------------------------

    def load_android_avds(self):
        process = subprocess.Popen([self.android, "list", "avd", "-c"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        self.avds = result.split()

    def select_android_target(self, select):
        if select < 0:
            return
        target = self.targets[select]
        if (target == "emulator"):
            self.load_android_avds()
            self.show_quick_panel(self.avds, self.select_android_avd)
        else:
            self.run_titanium(["--target", target])

    def select_android_avd(self, select):
        if select < 0:
            return
        self.run_titanium(["--avd-id", self.avds[select]])

    #--------------------------------------------------------------
    # IOS
    #--------------------------------------------------------------

    def select_ios_target(self, select):
        if select < 0:
            return
        self.target = self.targets[select]
        if self.target == "simulator":
            self.simtype = ["non-retina", "retina", "retina-tall", "ipad"]
            self.show_quick_panel(self.simtype, self.select_ios_simtype)
        else:
            self.families = ["iphone", "ipad", "universal"]
            self.show_quick_panel(self.families, self.select_ios_family)

    def select_ios_simtype(self, select):
        if select < 0:
            return
        if (self.simtype[select] == 'non-retina'):
            # iphone 4
            simulatorType = 'iphone'
            simulatorDisplay = ''
            simulatorHeight = ''
        elif (self.simtype[select] == "retina"):
            simulatorType = 'iphone'
            simulatorDisplay = self.simulatorDisplay
            simulatorHeight = ''
        else:
            simulatorType = 'iphone'
            simulatorDisplay = self.simulatorDisplay
            simulatorHeight = self.simulatorHeight
        self.run_titanium(["--sim-type", simulatorType, simulatorDisplay, simulatorHeight])

    def select_ios_family(self, select):
        if select < 0:
            return
        self.family = self.families[select]
        self.load_ios_info()
        self.show_quick_panel(self.certs, self.select_ios_cert)

    def select_ios_cert(self, select):
        if select < 0:
            return
        self.cert = self.certs[select]
        self.show_quick_panel(self.profiles, self.select_ios_profile)

    def select_ios_profile(self, select):
        if select < 0:
            return
        name, profile = self.profiles[select]
        options = ["--target", self.target, "--pp-uuid", profile, "--device-family", self.family]
        if self.target == "device":
            options.extend(["--developer-name", self.cert])
        else:
            options.extend(["--distribution-name", self.cert])

        if self.target == "dist-adhoc":
            options.extend(["--output-dir", self.project_folder + "/dist"])

        self.run_titanium(options)

    def load_ios_info(self):
        process = subprocess.Popen([self.cli, "info", "--types", "ios", "--output", "json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        result, error = process.communicate()
        info = json.loads(result.decode('utf-8'))
        for name, obj in list(info.items()):
            if name == "iosCerts":
                for target, c in list(obj.items()):
                    if target == "wwdr" or (target == "devNames" and self.target != "device") or (target == "distNames" and self.target == "device"):
                        continue
                    l = []
                    for cert in c:
                        l.append(cert)
                    self.certs = l
            elif name == "iOSProvisioningProfiles":
                for target, p in list(obj.items()):
                    # TODO: figure out what to do with enterprise profiles
                    if (target == "development" and self.target == "device") or (target == "distribution" and self.target == "dist-appstore") or (target == "adhoc" and self.target == "dist-adhoc"):
                        l = []
                        for profile in p:
                            l.append([profile['name'], profile['uuid']])
                        self.profiles = l
