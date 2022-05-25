# py-jablotron6x
Library for interfacing with Jablotron 6x alarms by using the JA-80T serial cable.

Example usage:

```
python

>>> from jablotron import Jablotron6x
>>> with Jablotron6x("/dev/ttyUSB0") as j:
>>>   j.on_mode_change = lambda mode: print(str(mode))
>>>   j.send_keys('F06060')
>>>   j.send_keys('N')
```

More details about the [ja-6x protocol](https://github.com/pezinek/py-jablotron6x/wiki/Protocol) is in the wiki.

Note: the mqtt functionality from ja2mqtt.py has been moved to [pezinek/jablotron2mqtt](https://github.com/pezinek/jablotron2mqtt) so if you want to interface your jablotron6x alarm with e.g. Home Assistant, use that other repo. ja2mqtt.py from this repo will be dropped.
