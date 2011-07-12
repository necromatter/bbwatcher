#!/usr/local/python-2.6/bin/python
#
# Big Brother Watcher Client

import sys
#sys.path.append("/usr/lib64/python2.4/site-packages/wx-2.8-gtk2-unicode")
import os, re, time, string, threading, ConfigParser, wx
import wx.lib.hyperlink as hl
import wx.lib.buttons as buttons
from wx.lib.wordwrap import wordwrap

version = "0.2.1"
ID_ABOUT = 101
ID_EXIT  = 102
ID_PREFS = 103
TBMENU_SHOW = 104
TBMENU_HIDE = 105
ID_RECONNECT = 106
ID_DISCONNECT = 107
ID_OPEN_RED = 108
ID_OPEN_YELLOW = 109
ID_OPEN_PURPLE = 110

PROG_PATH = os.path.abspath(os.path.dirname(sys.argv[0]))
CONF_FILE = PROG_PATH + "/bbwatcher.conf"
DEFAULT_SOUND_RED = PROG_PATH + "/sounds/red_alert.wav"
DEFAULT_SOUND_YELLOW = PROG_PATH + "/sounds/yellow_alert.wav"
DEFAULT_SOUND_PURPLE = PROG_PATH + "/sounds/purple_alert.wav"
STATUS = "Offline"

# Button definitions
ID_START = wx.NewId()
ID_STOP  = wx.NewId()

# Define notification event for thread completion
EVT_RESULT_ID = wx.NewId() #**EVT HNDL**#

# Result function to handle binding a window to an event. #**EVT HNDL**#
def EVT_RESULT(win, func):
    win.Connect(-1, -1, EVT_RESULT_ID, func)

###########################################################################################################
# Class for a custom event handel. #**EVT HNDL**#
class ResultEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data"""

    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESULT_ID)
        self.data = data

###########################################################################################################
# Create the thread class for the socket
class socketThread(threading.Thread):

    def __init__( self, win ):
        self.win = win #**EVT HNDL**#
        """ Start the socket thread.
        This should only need to be called once when the client is started.
        It is broken into a seperate function since stopping needs to be
        handled by the GUI object."""
        import socket
        # Create the socket object.
	try:
            self.aaSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.runSocket = True
            self.socketOpen = False
	    threading.Thread.__init__( self )
	except socket.error, msg:
	    sys.stderr.write("[Error creating socket] %s\n" % msg[1])

    def run(self):
        """ Run the actual socket.
        After a socket is actually created with the object defined in
        __init__, then we will wait for something to happen. """
        global CONF_server_ip
        global CONF_server_port
	global STATUS

        try:
            self.aaSocket.connect((CONF_server_ip, int(CONF_server_port)))
            self.socketOpen = True

            # Send authentication information. Right now used for testing ONLY.
            #self.aaSocket.send("Here is the username.\n")
            #self.aaSocket.send("Here is the password.\n")

	    self.aaResponse = self.aaSocket.recv(1024)
	    STATUS = "Online"
	    while len(self.aaResponse):
		if self.runSocket is False: break
		wx.PostEvent(self.win, ResultEvent(self.aaResponse))
	   	self.aaResponse = self.aaSocket.recv(1024)

            # Close socket session when the client closes.
	    STATUS = "Offline"
	    wx.PostEvent(self.win, ResultEvent("Connection to server lost."))
            self.aaSocket.close()
            self.socketOpen = False
	    self.close()

        except Exception, e:
#	    print('something\'s wrong with %s:%d. Exception type is %s' % (CONF_server_ip, int(CONF_server_port), `e`))
	    STATUS = "Offline"
            wx.PostEvent(self.win, ResultEvent("Connection refused."))
            self.runSocket = False
            self.socketOpen = False

    def stop(self):
        STATUS = "Offline"
#        print("socket stop")
        # End the continuous socket loop in the socket thread.
        self.runSocket = False
	# Sends message to server so we can break from the loop.
        if (self.socketOpen == True):
	    self.aaSocket.send("close\n")
	else:
	    self.socketOpen = False
	    self.aaSocket.close()
	sys.exit()

###########################################################################################################
# Run a loop and attempt to reconnect to the server if it drops
class reconnectLoop(threading.Thread):
    def __init__( self, win, socket ):
	self.win = win
	self.socket = socket
	self.keeprunning = True
	self.active = True
        threading.Thread.__init__( self )

    def run(self):
	global STATUS

	try:
            while(self.keeprunning is True):
                time.sleep(1)
                if self.socket.runSocket is False:
                    wx.PostEvent(self.win, ResultEvent("Attempting to reconnect to server..."))
	            STATUS = "Connecting"
	            self.socket = socketThread(self.win)
	            self.socket.start()
#	    print("out of reconnectLoop")
	    self.active = False
	except Exception, e:
#	    print('Exception in reconnectLoop: %s' % `e`)
	    self.active = False

    def stop(self):
#	print("reconnectLoop stop")
	self.keeprunning = False

###########################################################################################################
# Defines the frame for popping up alert messages in an annoying fashion
# on the screen. The guarantees that someone will take notice.
class alertFrame(wx.MiniFrame):
    def __init__(
        self, parent, title, pos=wx.DefaultPosition, size=wx.DefaultSize,
        style=wx.DEFAULT_FRAME_STYLE, msg="No Message"
        ):

        wx.MiniFrame.__init__(self, parent, -1, title)
        self.panel = wx.Panel(self, -1)
        
        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.NORMAL, False))
        self.hSizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer1.Add ( ( 0, 0 ), 1, wx.EXPAND )

        alertarray = string.split(msg)
        self.SetBackgroundColour(alertarray[0])
        self.panel.SetBackgroundColour(alertarray[0])
        alertText = "Hostname: " + alertarray[1] + "\nService: " \
                    + alertarray[2] + "\nPriority: " + alertarray[3]
        self.alertURL = CONF_bburl + CONF_bbcgibin + "/bb-hostsvc.sh?HOST=" \
                    + alertarray[1] + "&SERVICE=" + alertarray[2]
        self._hyper = hl.HyperLinkCtrl(self.panel, wx.ID_ANY, alertText, URL=self.alertURL)
        self._hyper.Bind(hl.EVT_HYPERLINK_LEFT, self.OnLink)
        self._hyper.AutoBrowse(False)
        self._hyper.SetColours("BLACK", "BLACK", "PURPLE")
        self._hyper.EnableRollover(True)
        self._hyper.SetUnderlines(False, False, True)
        self._hyper.SetBold(True)
        self._hyper.UpdateLink()
        self.hSizer1.Add(self._hyper)
        self.hSizer1.Add ( ( 0, 0 ), 1, wx.EXPAND )

        self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer2.Add ( ( 0, 0 ), 1, wx.EXPAND )
        self.button = wx.Button(self.panel, -1, "Close Alert")
        self.hSizer2.Add(self.button, 0, wx.ALIGN_CENTER)
        self.Bind(wx.EVT_BUTTON, self.closeAlert, self.button)
        self.Bind(wx.EVT_CLOSE, self.closeAlertWindow)

        self.vSizer = wx.BoxSizer ( wx.VERTICAL )
        self.vSizer.Add ( ( 0, 0 ), 1, wx.EXPAND )
        self.vSizer.Add ( self.hSizer1, 0, wx.ALIGN_CENTER )
        self.vSizer.Add ( ( 0, 0 ), 1, wx.EXPAND )
        self.vSizer.Add ( self.hSizer2, 0, wx.ALIGN_CENTER )

        self.panel.SetSizerAndFit(self.vSizer)
        self.SetClientSize(self.panel.GetSize())
        self.Show(True)

    def OnLink(self, event):
        self._hyper.GotoURL(self.alertURL, True, True)

    def closeAlert(self, event):
        self.Close(True)

    def closeAlertWindow(self, event):
        self.Destroy()

###########################################################################################################
# The class for the Preferences menu option
class prefsFrame(wx.MiniFrame):
    def __init__(
        self, parent, title, pos=wx.DefaultPosition, size=wx.DefaultSize,
        style=wx.DEFAULT_FRAME_STYLE
        ):
        wx.MiniFrame.__init__(self, parent, -1, "Preferences",
                             style=wx.DEFAULT_FRAME_STYLE & ~ (wx.RESIZE_BORDER))
        panel = wx.Panel(self, -1, style=wx.BORDER_SUNKEN)

        global config
        global CONF_use_default_sound
        global CONF_alertsound_red
	global CONF_alertsound_yellow
	global CONF_alertsound_purple
        global CONF_enablesound
        global CONF_popups
        global CONF_prio_1_red
        global CONF_prio_2_red
        global CONF_prio_3_red
        global CONF_prio_1_yel
        global CONF_prio_2_yel
        global CONF_prio_3_yel
        global CONF_prio_1_pur
        global CONF_prio_2_pur
        global CONF_prio_3_pur
	global CONF_filterlist

# Load defaults
        config.read(CONF_FILE)
        self.temp_use_default_sound = config.get("default", "use_default_sound")
        CONF_alertsound_red = config.get("default", "alertsound_red")
	CONF_alertsound_yellow = config.get("default", "alertsound_yellow")
	CONF_alertsound_purple = config.get("default", "alertsound_purple")
        CONF_enablesound = config.get("default", "enable_sound")
        CONF_popups = config.get("default", "pop_ups")
        CONF_prio_1_red = config.get("alerts", "prio_1_red")
        CONF_prio_2_red = config.get("alerts", "prio_2_red")
        CONF_prio_3_red = config.get("alerts", "prio_3_red")
        CONF_prio_1_yel = config.get("alerts", "prio_1_yel")
        CONF_prio_2_yel = config.get("alerts", "prio_2_yel")
        CONF_prio_3_yel = config.get("alerts", "prio_3_yel")
        CONF_prio_1_pur = config.get("alerts", "prio_1_pur")
        CONF_prio_2_pur = config.get("alerts", "prio_2_pur")
        CONF_prio_3_pur = config.get("alerts", "prio_3_pur")
	CONF_filterlist = config.get("alerts", "filterlist")

        vsz = wx.BoxSizer(wx.VERTICAL)

### Alert Filter Checkboxes
        box3 = wx.StaticBox(panel, -1, "Alert Filter")
        box3_sz = wx.StaticBoxSizer(box3, wx.VERTICAL)

        self.text = wx.StaticText(panel, -1, "      Select which events you wish to be alerted on      ")
        box3_sz.Add(self.text, 0, wx.ALIGN_CENTER)
        self.text = wx.StaticText(panel, -1, "\n                                            Priority")
        box3_sz.Add(self.text)

        box3_grid = wx.FlexGridSizer(cols=4, hgap=7, vgap=4)
        self.text = wx.StaticText(panel, -1, "")
        box3_grid.Add(self.text)
        self.text = wx.StaticText(panel, -1, " 1")
        box3_grid.Add(self.text)
        self.text = wx.StaticText(panel, -1, " 2")
        box3_grid.Add(self.text)
        self.text = wx.StaticText(panel, -1, " 3")
        box3_grid.Add(self.text)
        self.text = wx.StaticText(panel, -1, "Red   ")
        box3_grid.Add(self.text)
        self.red1 = wx.CheckBox(panel, -1)
        self.red2 = wx.CheckBox(panel, -1)
        self.red3 = wx.CheckBox(panel, -1)
        box3_grid.AddMany([ self.red1, self.red2, self.red3 ])
        self.text = wx.StaticText(panel, -1, "Yellow   ")
        box3_grid.Add(self.text)
        self.yel1 = wx.CheckBox(panel, -1)
        self.yel2 = wx.CheckBox(panel, -1)
        self.yel3 = wx.CheckBox(panel, -1)
        box3_grid.AddMany([ self.yel1, self.yel2, self.yel3 ])
        self.text = wx.StaticText(panel, -1, "Purple   ")
        box3_grid.Add(self.text)
        self.pur1 = wx.CheckBox(panel, -1)
        self.pur2 = wx.CheckBox(panel, -1)
        self.pur3 = wx.CheckBox(panel, -1)
        box3_grid.AddMany([ self.pur1, self.pur2, self.pur3 ])

        box3_sz.Add(box3_grid, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        vsz.Add(box3_sz, 0, wx.ALIGN_CENTER|wx.ALL, 5)

        if re.search("[Ff]alse", str(CONF_prio_1_red)):
            self.red1.SetValue(False)
        else:
            self.red1.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_2_red)):
            self.red2.SetValue(False)
        else:
            self.red2.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_3_red)):
            self.red3.SetValue(False)
        else:
            self.red3.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_1_yel)):
            self.yel1.SetValue(False)
        else:
            self.yel1.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_2_yel)):
            self.yel2.SetValue(False)
        else:
            self.yel2.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_3_yel)):
            self.yel3.SetValue(False)
        else:
            self.yel3.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_1_pur)):
            self.pur1.SetValue(False)
        else:
            self.pur1.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_2_pur)):
            self.pur2.SetValue(False)
        else:
            self.pur2.SetValue(True)
        if re.search("[Ff]alse", str(CONF_prio_3_pur)):
            self.pur3.SetValue(False)
        else:
            self.pur3.SetValue(True)
###

### Alert Option Checkboxes
        box1 = wx.StaticBox(panel, -1, "Alert Options")
        box1_sz = wx.StaticBoxSizer(box1, wx.VERTICAL)
        
        checkbox_grid = wx.FlexGridSizer(cols=1, hgap=4, vgap=4)
        self.cb1 = wx.CheckBox(panel, -1, "Enable Alert Pop-ups                                           ")
        checkbox_grid.Add(self.cb1)
        if re.search("[Ff]alse", str(CONF_popups)):
            self.cb1.SetValue(False)
        else:
            self.cb1.SetValue(True)
        self.cb2 = wx.CheckBox(panel, -1, "Enable Sounds")
        checkbox_grid.Add(self.cb2)
        if re.search("[Ff]alse", str(CONF_enablesound)):
            self.cb2.SetValue(False)
        else:
            self.cb2.SetValue(True)

        box1_sz.Add(checkbox_grid, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        vsz.Add(box1_sz, 0, wx.ALIGN_CENTER|wx.ALL, 5)
###
     
### Alert sound box
        box2 = wx.StaticBox(panel, -1, "Alert Sounds")
        box2_sz = wx.StaticBoxSizer(box2, wx.VERTICAL)

        radio_grid = wx.FlexGridSizer(cols=1, hgap=4, vgap=4)
        self.radio_def = wx.RadioButton(panel, -1, "Use default sounds")
        self.Bind(wx.EVT_RADIOBUTTON, self.OnRadioDef, self.radio_def)
        radio_grid.Add(self.radio_def, 1, wx.LEFT, 5)
        self.radio_local = wx.RadioButton(panel, -1, "Use custom sound files")
        self.Bind(wx.EVT_RADIOBUTTON, self.OnRadioLocal, self.radio_local)
        self.radio_local.SetValue(1)
        radio_grid.Add(self.radio_local, 1, wx.LEFT, 5)
        box2_sz.Add(radio_grid, 0, wx.LEFT|wx.ALL, 5)
        if re.search("[Tt]rue", str(self.temp_use_default_sound)):
            self.temp_alertsound_red = DEFAULT_SOUND_RED
            self.temp_alertsound_yellow = DEFAULT_SOUND_YELLOW
            self.temp_alertsound_purple = DEFAULT_SOUND_PURPLE
            self.radio_def.SetValue(1)
            self.radio_local.SetValue(0)
        else:
            self.temp_alertsound_red = CONF_alertsound_red
            self.temp_alertsound_yellow = CONF_alertsound_yellow
            self.temp_alertsound_purple = CONF_alertsound_purple
            self.radio_def.SetValue(0)
            self.radio_local.SetValue(1)

### Alert Sound selection fields     
        file_grid = wx.FlexGridSizer(cols=3, hgap=4, vgap=4)

        self.text_red = wx.StaticText(panel, -1, "    Red Alert")
        file_grid.Add(self.text_red)
        self.tc_red = wx.TextCtrl(panel, -1, self.temp_alertsound_red, size=(100,-1), style=wx.TE_READONLY)
        file_grid.Add(self.tc_red)
        self.cs_button_red = wx.Button(panel, ID_OPEN_RED, "Change Sound")
        file_grid.Add(self.cs_button_red)
        if re.search("[Tt]rue", str(self.temp_use_default_sound)):
            self.text_red.Enable(False)
            self.tc_red.Enable(False)
            self.cs_button_red.Enable(False)
        else:
            self.text_red.Enable(True)
            self.tc_red.Enable(True)
            self.cs_button_red.Enable(True)

        self.text_yellow = wx.StaticText(panel, -1, "    Yellow Alert")
        file_grid.Add(self.text_yellow)
        self.tc_yellow = wx.TextCtrl(panel, -1, self.temp_alertsound_yellow, size=(100,-1), style=wx.TE_READONLY)
        file_grid.Add(self.tc_yellow)
        self.cs_button_yellow = wx.Button(panel, ID_OPEN_YELLOW, "Change Sound")
        file_grid.Add(self.cs_button_yellow)
        if re.search("[Tt]rue", str(self.temp_use_default_sound)):
            self.text_yellow.Enable(False)
            self.tc_yellow.Enable(False)
            self.cs_button_yellow.Enable(False)
        else:
            self.text_yellow.Enable(True)
            self.tc_yellow.Enable(True)
            self.cs_button_yellow.Enable(True)

        self.text_purple = wx.StaticText(panel, -1, "    Purple Alert")
        file_grid.Add(self.text_purple)
        self.tc_purple = wx.TextCtrl(panel, -1, self.temp_alertsound_purple, size=(100,-1), style=wx.TE_READONLY)
        file_grid.Add(self.tc_purple)
        self.cs_button_purple = wx.Button(panel, ID_OPEN_PURPLE, "Change Sound")
        file_grid.Add(self.cs_button_purple)
        if re.search("[Tt]rue", str(self.temp_use_default_sound)):
            self.text_purple.Enable(False)
            self.tc_purple.Enable(False)
            self.cs_button_purple.Enable(False)
        else:
            self.text_purple.Enable(True)
            self.tc_purple.Enable(True)
            self.cs_button_purple.Enable(True)

        box2_sz.Add(file_grid, 0, wx.ALIGN_CENTER|wx.ALL, 5)       
        vsz.Add(box2_sz, 0, wx.ALIGN_CENTER|wx.ALL, 5)
###

### Hostname filter

        box4 = wx.StaticBox(panel, -1, "Hostname Filter")
        box4_sz = wx.StaticBoxSizer(box4, wx.VERTICAL)
	filter_grid = wx.FlexGridSizer(cols=2, hgap=4, vgap=4)

        self.filterlist_field = wx.StaticText(panel, -1, "    RegEx")
        filter_grid.Add(self.filterlist_field)
        self.tc_filterlist = wx.TextCtrl(panel, -1, CONF_filterlist, size=(220,-1))
        filter_grid.Add(self.tc_filterlist)
	box4_sz.Add(filter_grid, 0, wx.ALIGN_CENTER|wx.ALL, 5)       
        vsz.Add(box4_sz, 0, wx.ALIGN_CENTER|wx.ALL, 5)
###

### Bottom buttons
        bottom_grid = wx.FlexGridSizer(cols=3, hgap=4, vgap=4)
        button = wx.Button(panel, wx.ID_OK)
        button.SetDefault()
        self.Bind(wx.EVT_BUTTON, self.applyClose, button)
        bottom_grid.Add(button)
        
        self.Applybutton = wx.Button(panel, wx.ID_APPLY)
#        self.Applybutton.Enable(True)
        self.Bind(wx.EVT_BUTTON, self.applyOnly, self.Applybutton)
        bottom_grid.Add(self.Applybutton)
        
        button = wx.Button(panel, wx.ID_CANCEL)
        self.Bind(wx.EVT_BUTTON, self.cancel, button)
        bottom_grid.Add(button)

        vsz.Add(bottom_grid, 0, wx.ALIGN_CENTER|wx.ALL, 5)
### 

### Finish out sizers and show panel
        panel.SetSizer(vsz)
        vsz.Fit(panel)
#        self.SetBestFittingSize()
	self.SetInitialSize()
        self.Show(True)
######################

# Event bindings
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.red1)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.red2)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.red3)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.yel1)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.yel2)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.yel3)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.pur1)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.pur2)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.pur3)

        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.cb1)
        self.Bind(wx.EVT_CHECKBOX, self.EvtCheckBox, self.cb2)
        self.Bind(wx.EVT_BUTTON, self.OnFileOpenDialogRed, id=ID_OPEN_RED)
        self.Bind(wx.EVT_BUTTON, self.OnFileOpenDialogYellow, id=ID_OPEN_YELLOW)
        self.Bind(wx.EVT_BUTTON, self.OnFileOpenDialogPurple, id=ID_OPEN_PURPLE)
        self.Bind(wx.EVT_CLOSE, self.closeSettings)

    def OnRadioDef( self, event ):
        self.text_red.Enable(False)
        self.tc_red.Enable(False)
        self.cs_button_red.Enable(False)
        self.temp_alertsound_red = str(DEFAULT_SOUND_RED)

        self.text_yellow.Enable(False)
        self.tc_yellow.Enable(False)
        self.cs_button_yellow.Enable(False)
        self.temp_alertsound_yellow = str(DEFAULT_SOUND_YELLOW)

        self.text_purple.Enable(False)
        self.tc_purple.Enable(False)
        self.cs_button_purple.Enable(False)
        self.temp_alertsound_purple = str(DEFAULT_SOUND_PURPLE)

        self.Applybutton.Enable(True)
        self.temp_use_default_sound = True

    def OnRadioLocal( self, event ):
        self.text_red.Enable(True)
        self.tc_red.Enable(True)
        self.cs_button_red.Enable(True)
        self.temp_alertsound_red = CONF_alertsound_red

        self.text_yellow.Enable(True)
        self.tc_yellow.Enable(True)
        self.cs_button_yellow.Enable(True)
        self.temp_alertsound_yellow = CONF_alertsound_yellow

        self.text_purple.Enable(True)
        self.tc_purple.Enable(True)
        self.cs_button_purple.Enable(True)
        self.temp_alertsound_purple = CONF_alertsound_purple

        self.Applybutton.Enable(True)
        self.temp_use_default_sound = False

    def OnSize(self, evt):
        self.Refresh()

    def EvtCheckBox(self, event):
        self.Applybutton.Enable(True)

    def OnFileOpenDialogRed(self, evt):
        dlg = wx.FileDialog(self,
                            defaultDir = os.getcwd(),
                            wildcard = "*.wav",
                            style = wx.OPEN | wx.CHANGE_DIR)

        if dlg.ShowModal() == wx.ID_OK:
            self.temp_alertsound_red = dlg.GetPath()
            self.tc.Replace(-1, -1, self.temp_alertsound_red)
            self.Applybutton.Enable(True)
        dlg.Destroy()

    def OnFileOpenDialogYellow(self, evt):
        dlg = wx.FileDialog(self,
                            defaultDir = os.getcwd(),
                            wildcard = "*.wav",
                            style = wx.OPEN | wx.CHANGE_DIR)

        if dlg.ShowModal() == wx.ID_OK:
            self.temp_alertsound_yellow = dlg.GetPath()
            self.tc.Replace(-1, -1, self.temp_alertsound_yellow)
            self.Applybutton.Enable(True)
        dlg.Destroy()

    def OnFileOpenDialogPurple(self, evt):
        dlg = wx.FileDialog(self,
                            defaultDir = os.getcwd(),
                            wildcard = "*.wav",
                            style = wx.OPEN | wx.CHANGE_DIR)

        if dlg.ShowModal() == wx.ID_OK:
            self.temp_alertsound_purple = dlg.GetPath()
            self.tc.Replace(-1, -1, self.temp_alertsound_purple)
            self.Applybutton.Enable(True)
        dlg.Destroy()
      
# Write the settings to current vars and config file
    def applyOnly(self, event):
        global CONF_popups
        global CONF_enablesound
        global CONF_alertsound_red
        global CONF_alertsound_yellow
        global CONF_alertsound_purple
        global CONF_prio_1_red
        global CONF_prio_2_red
        global CONF_prio_3_red
        global CONF_prio_1_yel
        global CONF_prio_2_yel
        global CONF_prio_3_yel
        global CONF_prio_1_pur
        global CONF_prio_2_pur
        global CONF_prio_3_pur
	global CONF_filterlist
        
        CONF_prio_1_red = self.red1.GetValue()
        CONF_prio_2_red = self.red2.GetValue()
        CONF_prio_3_red = self.red3.GetValue()
        CONF_prio_1_yel = self.yel1.GetValue()
        CONF_prio_2_yel = self.yel2.GetValue()
        CONF_prio_3_yel = self.yel3.GetValue()
        CONF_prio_1_pur = self.pur1.GetValue()  
        CONF_prio_2_pur = self.pur2.GetValue()
        CONF_prio_3_pur = self.pur3.GetValue()
        CONF_popups = self.cb1.GetValue()
        CONF_enablesound = self.cb2.GetValue()
        CONF_alertsound_red = self.temp_alertsound_red
        CONF_alertsound_yellow = self.temp_alertsound_yellow
        CONF_alertsound_purple = self.temp_alertsound_purple
        CONF_use_default_sound = self.temp_use_default_sound
	CONF_filterlist = self.tc_filterlist.GetValue()
        config.set("alerts", "prio_1_red", CONF_prio_1_red)
        config.set("alerts", "prio_2_red", CONF_prio_2_red)
        config.set("alerts", "prio_3_red", CONF_prio_3_red)
        config.set("alerts", "prio_1_yel", CONF_prio_1_yel)
        config.set("alerts", "prio_2_yel", CONF_prio_2_yel)
        config.set("alerts", "prio_3_yel", CONF_prio_3_yel)
        config.set("alerts", "prio_1_pur", CONF_prio_1_pur)
        config.set("alerts", "prio_2_pur", CONF_prio_2_pur)
        config.set("alerts", "prio_3_pur", CONF_prio_3_pur)
        config.set("default", "pop_ups", CONF_popups)
        config.set("default", "enable_sound", CONF_enablesound)
        config.set("default", "alertsound_red", CONF_alertsound_red)
        config.set("default", "alertsound_yellow", CONF_alertsound_yellow)
        config.set("default", "alertsound_purple", CONF_alertsound_purple)
        config.set("default", "use_default_sound", CONF_use_default_sound)
	config.set("alerts", "filterlist", CONF_filterlist)
        fname = open(CONF_FILE,"w")
        config.write(fname)
#        self.Applybutton.Enable(False)

# Write the settings to file and close window
    def applyClose(self, event):        
        global CONF_popups
        global CONF_enablesound
        global CONF_alertsound_red
        global CONF_alertsound_yellow
        global CONF_alertsound_purple
        global CONF_prio_1_red
        global CONF_prio_2_red
        global CONF_prio_3_red
        global CONF_prio_1_yel
        global CONF_prio_2_yel
        global CONF_prio_3_yel
        global CONF_prio_1_pur
        global CONF_prio_2_pur
        global CONF_prio_3_pur
	global CONF_filterlist
        
        CONF_prio_1_red = self.red1.GetValue()
        CONF_prio_2_red = self.red2.GetValue()
        CONF_prio_3_red = self.red3.GetValue()
        CONF_prio_1_yel = self.yel1.GetValue()
        CONF_prio_2_yel = self.yel2.GetValue()
        CONF_prio_3_yel = self.yel3.GetValue()
        CONF_prio_1_pur = self.pur1.GetValue()  
        CONF_prio_2_pur = self.pur2.GetValue()
        CONF_prio_3_pur = self.pur3.GetValue()
        CONF_popups = self.cb1.GetValue()
        CONF_enablesound = self.cb2.GetValue()
        CONF_alertsound_red = self.temp_alertsound_red
        CONF_alertsound_yellow = self.temp_alertsound_yellow
        CONF_alertsound_purple = self.temp_alertsound_purple
        CONF_use_default_sound = self.temp_use_default_sound
	CONF_filterlist = self.tc_filterlist.GetValue()
        config.set("alerts", "prio_1_red", CONF_prio_1_red)
        config.set("alerts", "prio_2_red", CONF_prio_2_red)
        config.set("alerts", "prio_3_red", CONF_prio_3_red)
        config.set("alerts", "prio_1_yel", CONF_prio_1_yel)
        config.set("alerts", "prio_2_yel", CONF_prio_2_yel)
        config.set("alerts", "prio_3_yel", CONF_prio_3_yel)
        config.set("alerts", "prio_1_pur", CONF_prio_1_pur)
        config.set("alerts", "prio_2_pur", CONF_prio_2_pur)
        config.set("alerts", "prio_3_pur", CONF_prio_3_pur)
        config.set("default", "pop_ups", CONF_popups)
        config.set("default", "enable_sound", CONF_enablesound)
        config.set("default", "alertsound_red", CONF_alertsound_red)
        config.set("default", "alertsound_yellow", CONF_alertsound_yellow)
        config.set("default", "alertsound_purple", CONF_alertsound_purple)
        config.set("default", "use_default_sound", CONF_use_default_sound)
	config.set("alerts", "filterlist", CONF_filterlist)
        fname = open(CONF_FILE,"w")
        config.write(fname)
        self.Close(True)

    def cancel(self, event):
        self.Close(True)

    def closeSettings(self, event):
        self.Destroy()

##########################################################################################################
# This class inherits from the class wxFrame and gives more information about
# the formating and layout of the main frames of the application.
class mainFrame(wx.Frame):
    def __init__(self, parent, ID, title):
        wx.Frame.__init__(self, parent, ID, title,
                         wx.DefaultPosition, wx.Size(400, 150),
                         style = wx.DEFAULT_FRAME_STYLE & ~ (wx.MINIMIZE_BOX)) # No minimizing to taskbar
## Read in the config.ini file
        global config
        global CONF_server_ip
        global CONF_server_port
        global CONF_use_default_sound
        global CONF_alertsound_red
        global CONF_alertsound_yellow
        global CONF_alertsound_purple
        global CONF_enablesound
        global CONF_popups
        global CONF_bburl
        global CONF_bbcgibin
        global CONF_prio_1_red
        global CONF_prio_2_red
        global CONF_prio_3_red
        global CONF_prio_1_yel
        global CONF_prio_2_yel
        global CONF_prio_3_yel
        global CONF_prio_1_pur
        global CONF_prio_2_pur
        global CONF_prio_3_pur
	global CONF_filterlist
        
        config = ConfigParser.ConfigParser()
        config.read(CONF_FILE)
        CONF_server_ip = config.get("server", "server_ip")
        CONF_server_port = config.get("server", "server_port")
        CONF_use_default_sound = config.get("default", "use_default_sound")
        CONF_alertsound_red = config.get("default", "alertsound_red")
        CONF_alertsound_yellow = config.get("default", "alertsound_yellow")
        CONF_alertsound_purple = config.get("default", "alertsound_purple")
        CONF_enablesound = config.get("default", "enable_sound")
        CONF_popups = config.get("default", "pop_ups")
        CONF_bburl = config.get("server", "url")
        CONF_bbcgibin = config.get("server", "cgibin")
        CONF_prio_1_red = config.get("alerts", "prio_1_red")
        CONF_prio_2_red = config.get("alerts", "prio_2_red")
        CONF_prio_3_red = config.get("alerts", "prio_3_red")
        CONF_prio_1_yel = config.get("alerts", "prio_1_yel")
        CONF_prio_2_yel = config.get("alerts", "prio_2_yel")
        CONF_prio_3_yel = config.get("alerts", "prio_3_yel")
        CONF_prio_1_pur = config.get("alerts", "prio_1_pur")
        CONF_prio_2_pur = config.get("alerts", "prio_2_pur")
        CONF_prio_3_pur = config.get("alerts", "prio_3_pur")
	CONF_filterlist = config.get("alerts", "filterlist")
#########

        if re.search("[Tt]rue", str(CONF_use_default_sound)):
            CONF_alertsound_red = DEFAULT_SOUND_RED
            CONF_alertsound_yellow = DEFAULT_SOUND_YELLOW
            CONF_alertsound_purple = DEFAULT_SOUND_PURPLE

        self.log = wx.TextCtrl(self, -1,
                              style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)
        wx.Log_SetActiveTarget(alertLog(self.log))
        self.statusbar = self.CreateStatusBar()
	self.statusbar.SetFieldsCount(2)
        self.statusbar.SetStatusWidths([-1, -1])

	##### Title bar menus
        menuBar = wx.MenuBar()
        fileMenu = wx.Menu()
#        fileMenu.AppendSeparator()
        fileMenu.Append(ID_EXIT, "E&xit", "Terminate the program")
        menuBar.Append(fileMenu, "&File");

#	toolsMenu = wx.Menu()
#	toolsMenu.Append(ID_DISCONNECT, "&Disconnect", "Disconnect from server")
#	toolsMenu.Append(ID_RECONNECT, "&Reconnect", "Reconnect to server")
#	menuBar.Append(toolsMenu, "&Tools");

	editMenu = wx.Menu()
	editMenu.Append(ID_PREFS, "&Preferences", "Change program settings")
	menuBar.Append(editMenu, "&Edit");

	helpMenu = wx.Menu()
	helpMenu.Append(ID_ABOUT, "&About", "About this program")
	menuBar.Append(helpMenu, "&Help")
	
        self.SetMenuBar(menuBar)

#        EVT_MENU(self, ID_ABOUT, self.OnAbout)
#        EVT_MENU(self, ID_EXIT, self.agentExit)
#        EVT_MENU(self, ID_PREFS, self.OnPrefs)
##	EVT_MENU(self, ID_RECONNECT, self.Reconnect)
##	EVT_MENU(self, ID_DISCONNECT, self.Disconnect)
	#####

        wx.EVT_CLOSE(self,self.OnTaskBarHide) # Clicking X to close the window minimizes to systray

        # Setup a taskbar icon, and catch some events from it.
        bbIcon = wx.Icon(PROG_PATH + "/bitmaps/bbred.ico", wx.BITMAP_TYPE_ICO)
        self.tbicon = wx.TaskBarIcon()
        self.tbicon.SetIcon(bbIcon, "Big Brother Watcher v%s" % version)
        self.SetIcon(bbIcon)
        wx.EVT_TASKBAR_LEFT_DCLICK(self.tbicon, self.OnTaskBarActivate)
        wx.EVT_TASKBAR_RIGHT_UP(self.tbicon, self.OnTaskBarMenu)
#        EVT_MENU(self.tbicon, TBMENU_SHOW, self.OnTaskBarActivate)
#        EVT_MENU(self.tbicon, TBMENU_HIDE, self.OnTaskBarHide)
#        EVT_MENU(self.tbicon, ID_EXIT, self.agentExit)
#        EVT_MENU(self.tbicon, ID_ABOUT, self.OnAbout)

        # Set up event handler for any worker thread results.
        EVT_RESULT(self,self.OnResult) #**EVT HNDL**#

        ################# Initialize the socket thread.
        hostport = string.join((str(CONF_server_ip), str(CONF_server_port)), ':')
	wx.LogMessage('Connecting to Big Brother server at %s...' % hostport)
	self.statusbar.SetStatusText("Status: Connecting", 0)
        self.sessionSocket = socketThread(self)
        self.sessionSocket.start()
	self.statusbar.SetStatusText("Status: %s" % STATUS, 0)

        ################# Start the reconnect loop
	self.reconnectLoop = reconnectLoop(self, self.sessionSocket)
        self.reconnectLoop.start()


    # Recieves event data from thread. #**EVT HNDL**#
    def OnResult(self, event):
	global STATUS
	MATCHED = False
	if re.search("[a-zA-Z]", str(event.data)):
	    self.statusbar.SetStatusText("Status: %s" % STATUS, 0)
            # Process results here.
            if re.search("Closing session . . .", str(event.data)):
                wx.LogMessage("Closing session . . .")
            else:
                wx.LogMessage('%s' % event.data)
                alertarray = string.split(event.data)
		filterlist_array = string.split(CONF_filterlist)
		for filteritem in filterlist_array:
#		    print "%s : %s", filteritem, alertarray[1]
		    if re.search(str(filteritem), str(alertarray[1])):
			MATCHED = True

		if MATCHED is True:
                    if re.search("red", str(alertarray[0])):
		        alertsound = CONF_alertsound_red
                        if alertarray[3] is "1":
                            send_event = CONF_prio_1_red
                        elif alertarray[3] is "2":
                            send_event = CONF_prio_2_red
                        elif alertarray[3] is "3":
                            send_event = CONF_prio_3_red
                        else:
                            send_event = CONF_prio_1_red
                    elif re.search("yellow", str(alertarray[0])):
		        alertsound = CONF_alertsound_yellow
                        if alertarray[3] is "1":
                            send_event = CONF_prio_1_yel
                        elif alertarray[3] is "2":
                            send_event = CONF_prio_2_yel
                        elif alertarray[3] is "3":
                            send_event = CONF_prio_3_yel
                        else:
                            send_event = CONF_prio_1_yel
                    elif re.search("purple", str(alertarray[0])):
		        alertsound = CONF_alertsound_purple
                        if alertarray[3] is "1":
                            send_event = CONF_prio_1_pur
                        elif alertarray[3] is "2":
                            send_event = CONF_prio_2_pur
                        elif alertarray[3] is "3":
                            send_event = CONF_prio_3_pur
                        else:
                            send_event = CONF_prio_1_pur
                    else:
                        send_event = "False"
		else:
		    send_event = "False"

                if (event.data == "Connection established!" or
                    event.data == "Server quitting" or
                    event.data == "2 Connection refused."):
                    send_event = "False"

                if re.search("[Tt]rue", str(send_event)):
                    if re.search("[Tt]rue", str(CONF_popups)):
                        alertWin = alertFrame(self, "Big Brother Alert!",
                            style=wx.DEFAULT_FRAME_STYLE | wx.TINY_CAPTION_HORIZ,
                            msg=event.data)
                        alertWin.SetSize((300, 200))
                        alertWin.SetPosition((400, 300))
                        alertWin.Show(True)
                        alertWin.CenterOnScreen()
                    if re.search("[Tt]rue", str(CONF_enablesound)):
                        sound = wx.Sound(alertsound)
                        sound.Play(wx.SOUND_ASYNC)
	else:
	    STATUS = "Offline"
	    self.statusbar.SetStatusText("Status: %s" % STATUS, 0)
            wx.LogMessage("2 Connection with server lost.")
            send_event = False


#            while ( STATUS != "Online" ):
#	        self.sessionSocket.socketOpen = False 
#	        self.sessionSocket.runSocket = False
#	        self.sessionSocket.stop()
#	        wx.LogMessage("Attempting to reconnect to server...")
#        	self.statusbar.SetStatusText("Status: Connecting", 0)
#		self.sessionSocket = socketThread(self)
#		self.sessionSocket.start()
#		time.sleep(5)

        # In either event, the worker is done.
        self.worker = None

    def OnPrefs(self, event):
        settingsWin = prefsFrame(self, "Settings", style=wx.DEFAULT_FRAME_STYLE)
        settingsWin.Show(True)
        settingsWin.CenterOnScreen()

    def OnAbout(self, event):
        dlg = wx.MessageDialog(self, "This client connects directly to the Big Brother display server "
                                    "and relays events instantly as they arrive. Use the Hide and Show "
                                    "commands from the system tray menu to hide/view the running history "
                                    "of alerts.\n\n"
                                    "Keep in mind that this is a work in progress, but bug reports\n"
                                    "and suggestions are welcome. :)\n\n"
                                    "Authors: Matthew Epp (matthew.epp@us.army.mil)\n"
                                    "         Brent Scott (brent.r.scott@us.army.mil)\n",
                                    "Big Brother Watcher version %s" % version,
                                    wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.CenterOnScreen()
        dlg.Destroy()

    def agentExit(self, event):
#	print("exit 0")
	self.reconnectLoop.stop()
#	print("exit 1")
	while(self.reconnectLoop.active is True):
#	    print("exit 2")
	    time.sleep(1)
#	print("exit 3")
        self.sessionSocket.stop()
#	print("exit 4")
        self.Close(True)
        self.tbicon.Destroy()
        sys.exit()

    def Reconnect(self, event):
	if (self.sessionSocket.runSocket is True):
	    wx.LogMessage("Still connected.")
	else:
	    wx.LogMessage("Attempting to reconnect to server...")
	    self.statusbar.SetStatusText("Status: Connecting", 0)
	    self.sessionSocket = socketThread(self)
	    self.sessionSocket.start()

	self.statusbar.SetStatusText("Status: %s" % STATUS, 0)

    def OnCloseWindow(self, event):
        self.dying = True
        self.window = None
        self.mainmenu = None
        app.keepGoing = False
        self.Destroy()

    # Fixed this so double-clicking the systray icon both hides
    # and restores the main frame
    def OnTaskBarActivate(self, evt):
        if self.IsShown():
            self.Show(False)
            wx.GetApp().ProcessIdle()
        else:
            if self.IsIconized():
                self.Iconize(False)
            if not self.IsShown():
                self.Show(True)
            wx.GetApp().ProcessIdle()
            self.Raise()

    def OnTaskBarMenu(self, evt):
        menu = wx.Menu()
        menu.Append(TBMENU_SHOW, "&Show Log Window")
        menu.Append(TBMENU_HIDE, "&Hide Log Window")
        menu.AppendSeparator()
        menu.Append(ID_ABOUT, "&About")
        menu.Append(ID_EXIT, "&Exit")
        self.tbicon.PopupMenu(menu)
        menu.Destroy()
        wx.GetApp().ProcessIdle()

    def OnTaskBarHide(self, evt):
        self.Show(False)
        wx.GetApp().ProcessIdle()

    def OnIconfiy(self, evt):
        self.Show(False)
        evt.Skip()

    def OnMaximize(self, evt):
        evt.Skip()

##########################################################################################################
# Creates and alert log event to print into a window.
class alertLog(wx.PyLog):
    def __init__(self, textCtrl, logTime=0):
        wx.PyLog.__init__(self)
        self.tc = textCtrl
        self.logTime = logTime

    def DoLogString(self, message, timeStamp):
        message = time.strftime("%X", time.localtime(timeStamp)) + \
                ": " + message
        if self.tc:
            self.tc.AppendText(message + '\n')
	self.Flush()

##########################################################################################################
# This class creates the main display window which controls the alerting
# agent.
class mainDisp(wx.App):
    def OnInit(self):
        initMain = mainFrame(None, -1, "Big Brother Watcher v%s" % version)
        initMain.Show(True)
        initMain.CenterOnScreen()

	initMain.Connect(ID_ABOUT, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.OnAbout)
	initMain.Connect(ID_EXIT, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.agentExit)
	initMain.Connect(ID_PREFS, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.OnPrefs)
	initMain.Connect(ID_RECONNECT, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.Reconnect)
	initMain.Connect(ID_DISCONNECT, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.Disconnect)

	initMain.tbicon.Connect(TBMENU_SHOW, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.OnTaskBarActivate)
	initMain.tbicon.Connect(TBMENU_HIDE, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.OnTaskBarHide)
	initMain.tbicon.Connect(ID_EXIT, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.agentExit)
	initMain.tbicon.Connect(ID_ABOUT, -1, wx.wxEVT_COMMAND_MENU_SELECTED, initMain.OnAbout)

        self.SetTopWindow(initMain)
        self.keepGoing = True
        return True

# Call to the main loop in the GUI object.
mainAlert = mainDisp(0)
mainAlert.MainLoop()
