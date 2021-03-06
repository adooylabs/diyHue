import json
from subprocess import check_output

import requests

import logManager
from functions import light_types, nextFreeId
from functions.colors import convert_rgb_xy, convert_xy, hsv_to_rgb, rgbBrightness

logging = logManager.logger.get_logger(__name__)

def _get_rgb():
    light_type = {"type": "Extended color light", "swversion": "1.46.13_r26312", "manufacturername": "ESPHome"}
    light_type.state = {"on": False, "bri": 254, "hue": 0, "sat": 0, "xy": [0.0, 0.0],
                        "alert": "none", "effect": "none", "colormode": "xy", "reachable": True}
    light_types.config = {"archetype": "sultanbulb", "function": "mixed", "direction": "omnidirectional"}
    return light_type

def _get_dimmable():
    light_type = {"type": "Dimmable light", "swversion": "1.46.13_r26312", "manufacturername": "ESPHome"}
    light_type.state = {"on": False, "bri": 254, "alert": "none", "reachable": True}
    light_type.config = {"archetype": "classicbulb", "function": "mixed", "direction": "omnidirectional"}
    return light_type

def _get_toggle():
    light_type = {"type": "On/Off plug-in unit", "swversion": "V1.04.12", "manufacturername": "ESPHome"}
    light_type.state = {"on": False, "alert": "none", "reachable": True}
    light_type.config = {"archetype": "classicbulb", "function": "mixed", "direction": "omnidirectional"}
    return light_type

def getRequest(address, request_data, timeout=3):

    head = {"Content-type": "application/json"}
    response = requests.get("http://" + address + request_data, timeout=timeout, headers=head)
    return response.text

def postRequest(address, request_data, timeout=3):
    head = {"Content-type": "application/json"}
    response = requests.post("http://" + address + request_data, timeout=3, headers=head)
    return response.text

def addRequest(request_data, data_type, new_data):
    if ("?" in request_data):
        request_data = request_data + "&" + str(data_type) + "=" + str(new_data)
    else:
        request_data = request_data + "?" + str(data_type) + "=" + str(new_data)
    return request_data

def getLightType(light, address, data):
    request_data = ""
    if address["esphome_model"] == "ESPHome-RGBW":
        if "xy" in data: #revised according to hue api docs
            request_data = request_data + "/light/color_led"
        elif "ct" in data:
            request_data = request_data + "/light/white_led"
        elif ("hue" in data) or ("sat" in data):
            request_data = request_data + "/light/color_led"
        else:
            if light["state"]["colormode"] == "xy":
                request_data = request_data + "/light/color_led"
            elif light["state"]["colormode"] == "ct":
                request_data = request_data + "/light/white_led"
            elif light["state"]["colormode"] == "hs":
                request_data = request_data + "/light/color_led"
    elif address["esphome_model"] == "ESPHome-CT":
        request_data = request_data + "/light/white_led"
    elif address["esphome_model"] == "ESPHome-RGB":
        request_data = request_data + "/light/color_led"
    elif address["esphome_model"] == "ESPHome-Dimmable":
        request_data = request_data + "/light/dimmable_led"
    elif address["esphome_model"] == "ESPHome-Toggle":
        request_data = request_data + "/light/toggle_led"
    
    return request_data

def discover(bridge_config, new_lights):
    logging.debug("ESPHome: <discover> invoked!")

    device_ips = check_output("nmap  " + bridge_config["config"]["ipaddress"] + "/24 -p80 --open -n | grep report | cut -d ' ' -f5", shell=True).decode('utf-8').rstrip("\n").split("\n")
    del device_ips[-1] #delete last empty element in list
    for ip in device_ips:
        try:
            logging.debug ( "ESPHome: probing ip " + ip)
            response = requests.get ("http://" + ip + "/text_sensor/light_id", timeout=3)
            device = json.loads(response.text)['state'].split(';') #get device data
            mac = device[1]
            device_name = device[2]
            ct_boost = device[3]
            rgb_boost = device[4]
            if response.status_code == 200 and device[0] == "esphome_diyhue_light":
                logging.debug("ESPHome: Found " + device_name + " at ip " + ip)
                white_response = requests.get ("http://" + ip + "/light/white_led", timeout=3)
                color_response = requests.get ("http://" + ip + "/light/color_led", timeout=3)
                dim_response = requests.get ("http://" + ip + "/light/dimmable_led", timeout=3)
                toggle_response = requests.get ("http://" + ip + "/light/toggle_led", timeout=3)

                if (white_response.status_code != 200 and color_response.status_code != 200 and dim_response.status_code != 200 and toggle_response.status_code != 200):
                    logging.debug("ESPHome: Device has improper configuration! Exiting.")
                    raise
                elif (white_response.status_code == 200 and color_response.status_code == 200):
                    logging.debug("ESPHome: " + device_name + " is a RGBW ESPHome device")
                    properties = {"rgb": True, "ct": True, "ip": ip, "name": device_name, "id": mac, "mac": mac, "ct_boost": ct_boost, "rgb_boost": rgb_boost}
                    esphome_model = "ESPHome-RGBW"
                    modelid = "LCT015"
                    light_properties = light_types[modelid]
                elif (white_response.status_code == 200):
                    logging.debug("ESPHome: " + device_name + " is a CT ESPHome device")
                    properties = {"rgb": False, "ct": True, "ip": ip, "name": device_name, "id": mac, "mac": mac, "ct_boost": ct_boost, "rgb_boost": rgb_boost}
                    esphome_model = "ESPHome-CT"
                    modelid = "LWB010"
                    light_properties = light_types[modelid]
                elif (color_response.status_code == 200):
                    logging.debug("ESPHome: " + device_name + " is a RGB ESPHome device")
                    properties = {"rgb": True, "ct": False, "ip": ip, "name": device_name, "id": mac, "mac": mac, "ct_boost": ct_boost, "rgb_boost": rgb_boost}
                    esphome_model = "ESPHome-RGB"
                    modelid = esphome_model
                    light_properties = _get_rgb()
                elif (dim_response.status_code == 200):
                    logging.debug("ESPHome: " + device_name + " is a Dimmable ESPHome device")
                    properties = {"rgb": False, "ct": False, "ip": ip, "name": device_name, "id": mac, "mac": mac, "ct_boost": ct_boost, "rgb_boost": rgb_boost}
                    esphome_model = "ESPHome-Dimmable"
                    modelid = esphome_model
                    light_properties = _get_dimmable()
                elif (toggle_response.status_code == 200):
                    logging.debug("ESPHome: " + device_name + " is a Toggle ESPHome device")
                    properties = {"rgb": False, "ct": False, "ip": ip, "name": device_name, "id": mac, "mac": mac, "ct_boost": ct_boost, "rgb_boost": rgb_boost}
                    esphome_model = "ESPHome-Toggle"
                    modelid = esphome_model
                    light_properties = _get_toggle()
                else:
                    logging.debug("ESPHome: ip " + ip + " is unknown device")
                    raise

                device_exist = False
                for light in bridge_config["lights_address"].keys():
                    if bridge_config["lights_address"][light]["protocol"] == "esphome" and  bridge_config["lights_address"][light]["id"] == properties["id"]:
                        device_exist = True
                        bridge_config["lights_address"][light]["ip"] = properties["ip"]
                        bridge_config["lights_address"][light]["ct_boost"] = properties["ct_boost"]
                        bridge_config["lights_address"][light]["rgb_boost"] = properties["rgb_boost"]
                        logging.debug("ESPHome: light id " + properties["id"] + " already exists, updating device data...")
                        break
                if (not device_exist):
                    light_name = "ESPHome id " + properties["id"][-8:] if properties["name"] == "" else properties["name"]
                    logging.debug("ESPHome: Adding ESPHome " + properties["id"])
                    new_light_id = nextFreeId(bridge_config, "lights")
                    bridge_config["lights"][new_light_id] = {}
                    bridge_config["lights"][new_light_id]["state"] = light_properties["state"]
                    bridge_config["lights"][new_light_id]["type"] = light_properties["type"]
                    bridge_config["lights"][new_light_id]["name"] = light_name
                    bridge_config["lights"][new_light_id]["modelid"] = modelid
                    bridge_config["lights"][new_light_id]["manufacturername"] = light_properties["manufacturername"]
                    bridge_config["lights"][new_light_id]["swversion"] = light_properties["swversion"]
                    bridge_config["lights"][new_light_id]["config"] = light_properties["config"]
                    bridge_config["lights"][new_light_id]["uniqueid"] = mac
                    if modelid == "LCT015":
                        bridge_config["lights"][new_light_id]["capabilities"] = light_types[modelid]["capabilities"]
                    bridge_config["lights_address"][new_light_id] = {}
                    bridge_config["lights_address"][new_light_id]["ip"] = properties["ip"]
                    bridge_config["lights_address"][new_light_id]["id"] = properties["id"]
                    bridge_config["lights_address"][new_light_id]["protocol"] = "esphome"
                    bridge_config["lights_address"][new_light_id]["rgb_boost"] = rgb_boost
                    bridge_config["lights_address"][new_light_id]["ct_boost"] = ct_boost
                    bridge_config["lights_address"][new_light_id]["esphome_model"] = esphome_model

        except Exception as e:
            logging.debug("ESPHome: ip " + ip + " is unknown device, " + str(e))

def set_light(address, light, data, rgb = None):
    logging.debug("ESPHome: <set_light> invoked! IP=" + address["ip"])
    logging.debug(light["modelid"])
    logging.debug(data)

    ct_boost = int(address["ct_boost"])
    rgb_boost = int(address["rgb_boost"])
    request_data = ""
    if ("alert" in data) and (data['alert'] == "select"): #one breath cycle, temporary for now until breath implemented in esphome firmware
        request_data = request_data + "/switch/alert/turn_on"
    # elif ("alert" in data) and (data['alert'] == "lselect"): #15 second breath cycle
    #     request_data = request_data + "/switch/alert/turn_on"
    # elif ("alert" in data) and (data['alert'] == "none"):
    #     request_data = request_data + "/switch/alert/turn_off"
    else:
        request_data = request_data + getLightType(light, address, data)
        if "white_led" in request_data:
            postRequest(address["ip"], "/light/color_led/turn_off")
        else:
            postRequest(address["ip"], "/light/white_led/turn_off")
        if "on" in data:
            if not(data['on']):
                request_data = request_data + "/turn_off"
            else:
                request_data = request_data + "/turn_on"
        else:
            request_data = request_data + "/turn_on"
        if address["esphome_model"] is not "ESPHome-Toggle":
            if "bri" in data:
                brightness = int(data['bri'])
                if address["esphome_model"] == "ESPHome-RGBW":
                    if light["state"]["colormode"] == "ct":
                        brightness = ct_boost + brightness
                    elif light["state"]["colormode"] == "xy":
                        brightness = rgb_boost + brightness
                elif address["esphome_model"] == "ESPHome-CT":
                    brightness = ct_boost + brightness
                elif address["esphome_model"] == "ESPHome-RGB":
                    brightness = rgb_boost + brightness
                elif address["esphome_model"] == "ESPHome-Dimmable":
                    brightness = ct_boost + brightness
                if brightness > 255: # do not send brightness values over 255
                    brightness = 255
                request_data = addRequest(request_data, "brightness", brightness)
            if address["esphome_model"] in ["ESPHome-RGBW", "ESPHome-RGB", "ESPHome-CT"]:
                if ("xy" in data) and (address["esphome_model"] in ["ESPHome-RGBW", "ESPHome-RGB"]):
                    if rgb:
                        color = rgbBrightness(rgb, light["state"]["bri"])
                    else:
                        color = convert_xy(data['xy'][0], data['xy'][1], light["state"]["bri"])
                    request_data = addRequest(request_data, "r", color[0])
                    request_data = addRequest(request_data, "g", color[1])
                    request_data = addRequest(request_data, "b", color[2])
                elif "ct" in data and (address["esphome_model"] in ["ESPHome-RGBW", "ESPHome-CT"]):
                    request_data = addRequest(request_data, "color_temp", data['ct'])
                elif (("hue" in data) or ("sat" in data)) and (address["esphome_model"] in ["ESPHome-RGBW", "ESPHome-RGB"]):
                    if (("hue" in data) and ("sat" in data)):
                        hue = data['hue']
                        sat = data['sat']
                    elif "hue" in data:
                        hue = data['hue']
                        sat = light["state"]["sat"]
                    elif "sat" in data:
                        hue = light["state"]["hue"]
                        sat = data['sat']
                    if "bri" not in data:
                        bri = light["state"]["bri"]
                    else:
                        bri = data['bri']
                    color = hsv_to_rgb(hue, sat, bri)
                    request_data = addRequest(request_data, "r", color[0])
                    request_data = addRequest(request_data, "g", color[1])
                    request_data = addRequest(request_data, "b", color[2])
            if "transitiontime" in data:
                request_data = addRequest(request_data, "transition", data['transitiontime']/10)
            else: #Utilize default interval of 0.4
                request_data = addRequest(request_data, "transition", 0.4)

    postRequest(address["ip"], request_data)




def get_light_state(address, light):
    logging.debug("ESPHome: <get_light_state> invoked!")
    state = {}
    if address["esphome_model"] == "ESPHome-RGBW":
        white_response = requests.get ("http://" + address["ip"] + "/light/white_led", timeout=3)
        color_response = requests.get ("http://" + address["ip"] + "/light/color_led", timeout=3)
        white_device = json.loads(white_response.text) #get white device data
        color_device = json.loads(color_response.text) #get color device data
        if white_device['state'] == 'OFF' and color_device['state'] == 'OFF':
            state['on'] = False
        elif white_device['state'] == 'ON':
            state['on'] = True
            state['ct'] = int(white_device['color_temp'])
            state['bri'] = int(white_device['brightness'])
            state['colormode'] = "ct"
        elif color_device['state'] == 'ON':
            state['on'] = True
            state['xy'] = convert_rgb_xy(int(color_device['color']['r']), int(color_device['color']['g']), int(color_device['color']['b']))
            state['bri'] = int(color_device['brightness'])
            state['colormode'] = "xy"

    elif address["esphome_model"] == "ESPHome-CT":
        white_response = requests.get ("http://" + address["ip"] + "/light/white_led", timeout=3)
        white_device = json.loads(white_response.text) #get white device data
        if white_device['state'] == 'OFF':
            state['on'] = False
        elif white_device['state'] == 'ON':
            state['on'] = True
            state['ct'] = int(white_device['color_temp'])
            state['bri'] = int(white_device['brightness'])
            state['colormode'] = "ct"

    elif address["esphome_model"] == "ESPHome-RGB":
        color_response = requests.get ("http://" + address["ip"] + "/light/color_led", timeout=3)
        color_device = json.loads(color_response.text)
        if color_device['state'] == 'OFF':
            state['on'] = False
        elif color_device['state'] == 'ON':
            state['on'] = True
            state['xy'] = convert_rgb_xy(int(color_device['color']['r']), int(color_device['color']['g']), int(color_device['color']['b']))
            state['bri'] = int(color_device['brightness'])
            state['colormode'] = "xy"

    elif address["esphome_model"] == "ESPHome-Dimmable":
        dimmable_response = requests.get ("http://" + address["ip"] + "/light/dimmable_led", timeout=3)
        dimmable_device = json.loads(dimmable_response.text)
        if dimmable_device['state'] == 'OFF':
            state['on'] = False
        elif dimmable_device['state'] == 'ON':
            state['on'] = True
            state['bri'] = int(dimmable_device['brightness'])

    elif address["esphome_model"] == "ESPHome-Toggle":
        toggle_response = requests.get ("http://" + address["ip"] + "/light/toggle_led", timeout=3)
        toggle_device = json.loads(toggle_response.text)
        if toggle_device['state'] == 'OFF':
            state['on'] = False
        elif toggle_device['state'] == 'ON':
            state['on'] = True

    return state
