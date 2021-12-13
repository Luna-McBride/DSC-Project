#!/usr/bin/env python3

import requests
import json
import os
import sys
import time
import jsonpickle
from PIL import Image


#
# Use localhost & port 5000 if not specified by environment variable REST
#
REST = os.getenv("REST") or "localhost:5000"

##
# The following routine makes a JSON REST query of the specified type
# and if a successful JSON reply is made, it pretty-prints the reply
##


def mkReq(reqmethod, endpoint, data):
    print(f"Response to http://{REST}/{endpoint} request is")
    jsonData = json.dumps(data)
    response = reqmethod(f"http://{REST}/{endpoint}", data=jsonData,
                         headers={'Content-type': 'application/json'})
    if response.status_code == 200:
        jsonResponse = json.dumps(response.json(), indent=4, sort_keys=True)
        if endpoint == "api/getPlot":
            img = jsonpickle.decode(jsonResponse)
            imgLoad = Image.open(img)
            rgbIm = imgLoad.convert("RGB")
            rgbIm.save("loadImage.jpg")
        else:        
            print(jsonResponse)
        return
    else:
        print(
            f"response code is {response.status_code}, raw response is {response.text}")
        return response.text


mkReq(requests.post, "api/pullData",
      data={
          "city" : "seattle",
      }
      )

time.sleep(5)

mkReq(requests.post, "api/pullData",
      data={
          "city" : ["juneau", "sendai"],
      }
      )

time.sleep(5)

mkReq(requests.get, "api/getAll", data=None)

#mkReq(requests.get, "api/deleteCity", data = {"city" : "seattle"})

mkReq(requests.get, "api/getPlot",
      data={
          "city": ["juneau", "sendai"],
          "field": "tempmax"
      }
      )

sys.exit(0)
