# -------------------------------------------------------
# File name  : NAU7802.py
# Version    : 1.0
# Release    : 2024.03.27
# Author     : bill6300gp
# Description: The library of NAU7802 24bits-ADC for Pi Pico.
# -------------------------------------------------------
from machine import Pin, I2C, Timer
from utime import sleep
from micropython import const

#Status
Status_Inited      =const(0x80)
Status_EnDRDY      =const(0x40)
Status_EnTimer     =const(0x20)
Status_PowerOn     =const(0x10)
Status_PeriodicRead=const(0x08)
Status_ADCReady    =const(0x04)

maskGain=const(7)
Gain128 =const(7)
Gain64  =const(6)
Gain32  =const(5)
Gain16  =const(4)
Gain8   =const(3)
Gain4   =const(2)
Gain2   =const(1)
Gain1   =const(0)

maskSPS=const(0x70)
SPS320 =const(0x70)
SPS80  =const(0x30)
SPS40  =const(0x20)
SPS20  =const(0x10)
SPS10  =const(0x00)

class NAU7802:
    __Status=0x00
    __CTRL1 =0x00
    __CTRL2 =0x00
    __I2CBus =None
    __PinDRDY=None
    __Tim    =None
    
    __SPS    =0
    __dataI  =0
    __dataX  =[-10,-9,-8,-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7,8,9,10]
    __dataY  =[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
    __LinRegA=0.0
    __LinRegB=0.0
    __LinRegE=0.0
    __Check  =0
    
    MeanValue=0.0
    LinRegVal=0.0
    ValStable=0
    def __init__(self, SCL=5, SDA=4, PinDRDY=-1, Ch=1, Gain=Gain128, ADCSPS=SPS80, TimerPort=None):
        if ((SCL%4)==1 and (SDA%4)==0):
            self.__I2CBus= I2C(0,scl=Pin(SCL),sda=Pin(SDA),freq=100000)
            #print('Create I2C0')
        elif ((SCL%4)==3 and (SDA%4)==2):
            self.__I2CBus= I2C(1,scl=Pin(SCL),sda=Pin(SDA),freq=100000)
            #print('Create I2C1')
        else:
            #print('No I2C')
            return None
        
        if 0x2A in self.__I2CBus.scan():
            if PinDRDY>=0 and PinDRDY<=22:
                self.__PinDRDY=Pin(PinDRDY, mode=Pin.IN)
                self.__Status|=Status_EnDRDY
            if (Gain<=7 and Gain>=0) and ((ADCSPS>>4)==7 or ((ADCSPS>>4)<=3 and (ADCSPS>>4)>=0)):
                self.__CTRL1 |=(0x28|Gain)
                self.__CTRL2  =((self.__CTRL2&~maskSPS)|ADCSPS)
                if ADCSPS==SPS10: self.__SPS=10
                elif ADCSPS==SPS20: self.__SPS=20
                elif ADCSPS==SPS40: self.__SPS=40
                elif ADCSPS==SPS80: self.__SPS=80
                elif ADCSPS==SPS320: self.__SPS=320
                if TimerPort==None:
                    self.__Status|=Status_Inited
                else:
                    self.__Tim=TimerPort
                    self.__Status|=(Status_Inited|Status_EnTimer)
            else:
                return None
    
    def __del__(self):
        if self.__Status&Status_PeriodicRead: self.startReadADC(0)
        if self.__Status&Status_PowerOn: self.PowerOff()
        self.__Status=0x00
    
    def PowerOn(self):
        if (self.__Status&(Status_Inited|Status_PowerOn))==Status_Inited:
            # set Addr value: 0x00, 0x01, 0x02
            self.__I2CBus.writeto(0x2A,bytearray([0x00, 0x86, self.__CTRL1, self.__CTRL2]))
            # set Addr value: 0x15
            tmp=self.__I2CBus.readfrom_mem(0x2A,0x15,1)
            self.__I2CBus.writeto(0x2A,bytearray([0x15, ord(tmp)|0x30]))
            # set Addr value: 0x1C
            self.__I2CBus.writeto(0x2A,bytearray([0x1C, 0x80]))
            # set Addr value: 0x1B
            tmp=self.__I2CBus.readfrom_mem(0x2A,0x1B,1)
            self.__I2CBus.writeto(0x2A,bytearray([0x1B, ord(tmp)&0xBF]))
            self.__Status|=Status_PowerOn
            #Waiting ADC Data Ready
            while (self.__Status&Status_ADCReady)==0x00:
                tmp1=self.__I2CBus.readfrom_mem(0x2A,0x1F,1)
                tmp2=self.__I2CBus.readfrom_mem(0x2A,0x00,1)
                if (self.__Status&Status_EnDRDY and self.__PinDRDY.value()) or ((ord(tmp1)&0x0F)==0x0F and (ord(tmp2)&0x20)==0x20):
                    self.__Status|=Status_ADCReady
                sleep(0.1)
    
    def PowerOff(self):
        if self.__Status&Status_PowerOn:
            self.__I2CBus.writeto(0x2A,bytearray([0x00, 0x01]))
            self.__Status&=0xC0
    
    def getRawData(self):
        result=0
        if self.__Status&Status_ADCReady:
            tmp=self.__I2CBus.readfrom_mem(0x2A,0x12,3)
            result=(tmp[0]<<16)|(tmp[1]<<8)|tmp[2]
            if result&0x800000: result=(result&0x7FFFFF)-0x800000
        return result
    
    def updateADC(self, t):
        if self.__Status&Status_ADCReady:
            if self.__dataI<21:
                self.__dataY[self.__dataI]=self.getRawData()
                self.__dataI+=1
            else:
                self.__dataY.pop(0)
                self.__dataY.append(self.getRawData())
                (self.__LinRegA, self.__LinRegB, self.__LinRegE)=self.LinearReg(self.__dataX, self.__dataY)
                self.MeanValue=self.Average(self.__dataY)
                self.LinRegVal=self.__LinRegB
                if self.__LinRegE<200: self.ValStable=1
                else: self.ValStable=0
    
    def startReadADC(self, state=-1, Freq=10):
        if self.__Status&Status_ADCReady:
            if state==1 and (self.__Status&(Status_EnTimer|Status_PeriodicRead))==Status_EnTimer and (Freq>0 and Freq<=self.__SPS):
                self.__dataI  =0
                self.__LinRegA=0.0
                self.__LinRegB=0.0
                self.__LinRegE=0.0
                self.MeanValue=0.0
                self.LinRegVal=0.0
                self.ValStable=0
                self.__Check  =0
                self.__Tim.init(freq=Freq, mode=Timer.PERIODIC, callback=self.updateADC)
                self.__Status|=Status_PeriodicRead
                return 1
            elif state==0 and (self.__Status&Status_PeriodicRead):
                self.__Tim.init(callback=None)
                self.__Status&=~Status_PeriodicRead
                return 1
            else:
                return 0
    
    def Average(self, Y=[]):
        if len(Y)>1 and (type(Y[0])==int or type(Y[0])==float):
            return sum(Y)/len(Y)
        elif len(Y)==1:
            return Y
        else:
            return 0
    
    def LinearReg(self, X=[], Y=[]):
        if len(X)>2 and len(X)==len(Y) and (type(Y[0])==int or type(Y[0])==float):
            n=len(X)
            Sx=Sy=Sxx=Syy=Sxy=tmp=0.0
            for x, y in zip(X, Y):
                Sx +=x
                Sy +=y
                Sxx+=x*x
                Syy+=y*y
                Sxy+=x*y
            det = Sxx*n-Sx*Sx
            a=(Sxy*n-Sy*Sx)/det
            b=(Sxx*Sy-Sx*Sxy)/det
            
            for x, y in zip(X, Y):
                tmp+=abs(y-(a*x+b))
                e=tmp/n
            
            return a,b,e
        else:
            return 0,0,0
    
if __name__ == "__main__":
    try:
        Tim=Timer(-1)
        ADC=NAU7802(SCL=5, SDA=4, PinDRDY=-1, Gain=Gain128, ADCSPS=SPS80, TimerPort=Tim)
        sleep(0.1)
        ADC.PowerOn()
        sleep(0.1)
        if ADC.startReadADC(1,80):
            while True:
                print(ADC.MeanValue, ADC.LinRegVal, ADC.ValStable)
                sleep(0.2)
    except KeyboardInterrupt:
        if ADC.__Status&Status_PeriodicRead: ADC.startReadADC(0)
        if ADC.__Status&Status_PowerOn: ADC.PowerOff()
        machine.reset()
        pass
    except:
        pass
    finally:
        pass
    
