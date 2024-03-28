# RPi-pico-weight
The library of 24bits-ADC for Pi Pico combined with weight module.

---

## Description
The library of weight module can get raw data or calculated value with the process of the linear regression (Y=aX+b).
</br>
Combined with Timer, the data can updated periodically after startReadADC(state, Freq).
</br>
When using periodical read mode, the maximum value of frequency is 2 in HX711 module for stability and the setting of sample rate in NAU7802 module.
</br>
*Note: The data is raw value or calculated raw value in the library. The process of the converting raw value into weight will be written in main.py.

## Usage

### Hardware

   **Raspberry Pi pico boards:** pico or pico w
   </br>
   **ADC units:** HX711 via serial interface or NAU7802 via I2C protocol
   </br>

### Library Import

1. Using HX711 module:

   `import HX711`
   </br>
   `ADC=HX711.HX711(SCK=5, DOUT=4, ChMode=HX711.ChAx128, TimerPort=None)`

2. Using NAU7802 module:

   `import NAU7802`
   </br>
   `ADC=NAU7802.NAU7802(SCL=5, SDA=4, PinDRDY=-1, Gain=NAU7802.Gain128, ADCSPS=NAU7802.SPS80, TimerPort=None)`
   </br>
   </br>
   *Note: The Timer objects will be created in main.py and connect to the TimerPort.

### Get Raw Data

1. Get raw data in time:

   `ADC.getRawData()`

2. Get calculated data of the mean or linear regression after starting periodical read mode:
 
   `ADC.startReadADC(state=1, Freq=2)`
   </br>
   *Note: When starting successfully, the function will return 1.
   </br>
   The `ADC.MeanValue` is mean value and the `ADC.LinRegVal` is b value of the linear regression (Y=aX+b).
   </br>
   The value will be updated after 11th-sample in HX711 module and 21st-sample in NAU7802 module when starting periodical read mode.
   
3. On Stopping periodical read mode:

   `ADC.startReadADC(state=0)`
   </br>
   *Note: When stopping successfully, the function will return 1.
   
