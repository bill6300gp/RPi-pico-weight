# -------------------------------------------------------
# File name  : HX711.py
# Version    : 1.1
# Release    : 2024.03.28
# Author     : bill6300gp
# Description: The library of HX711 24bits-ADC for Pi Pico.
# -------------------------------------------------------
from machine import Pin, Timer
from utime import sleep, sleep_us
from micropython import const

#Status
MaskCanPeriodicRead=const(0xB0)
Status_Inited      =const(0x80)
Status_EnTimer     =const(0x20)
Status_PowerOn     =const(0x10)
Status_PeriodicRead=const(0x08)
Status_OutReady    =const(0x04)
#Channel and Gain
ChAx128=const(25)
ChBx32 =const(26)
ChAx64 =const(27)

class HX711:
    __Status =0x00
    __PinSCK =None
    __PinDOUT=None
    __ChMode =0
    __Tim    =None
    
    __SPS    =0
    __dataI  =0
    __dataX  =[-5,-4,-3,-2,-1,0,1,2,3,4,5]
    __dataY  =[0,0,0,0,0,0,0,0,0,0,0]
    __LinRegA=0.0
    __LinRegB=0.0
    __LinRegE=0.0
    __Check  =0
    
    MeanValue=0.0
    LinRegVal=0.0
    ValStable=0
    def __init__(self, SCK=-1, DOUT=-1, ChMode=ChAx128, TimerPort=None):
        if (SCK>=0 and SCK<=22) and (DOUT>=0 and DOUT<=22) and SCK!=DOUT and (ChMode>=25 and ChMode<=27):
            self.__PinSCK =Pin(SCK, mode=Pin.OUT, value=1)
            self.__PinDOUT=Pin(DOUT, mode=Pin.IN, pull=Pin.PULL_UP)
            self.__ChMode =ChMode
            if TimerPort==None:
                self.__Status=Status_Inited
            else:
                self.__Tim=TimerPort
                self.__Status=(Status_Inited|Status_EnTimer)
        else:
            return None
    
    def __del__(self):
        if self.__Status&Status_PeriodicRead: self.startReadADC(0)
        if self.__Status&Status_PowerOn: self.PowerOff()
        self.__Status=0x00
        
    def PowerOn(self):
        if (self.__Status&(Status_Inited|Status_PowerOn))==Status_Inited:
            self.__Status|=Status_PowerOn
            self.__PinDOUT.irq(trigger=Pin.IRQ_FALLING,handler=self.PinDOUT_IRQHandler)
            self.__PinSCK.value(0)
            while (self.__Status&Status_OutReady)==0x00: sleep_us(100)
            
    def PowerOff(self):
        if self.__Status&Status_PowerOn:
            self.__PinSCK.value(1)
            sleep_us(64)
            self.__Status&=0xE0
    
    def PinDOUT_IRQHandler(self, pin):
        self.__PinDOUT.irq(handler=None)
        if self.__Status&Status_PowerOn: self.__Status|=Status_OutReady
    
    def setChGain(self, ChMode):
        if (ChMode>=25 and ChMode<=27) and (self.__Status&Status_OutReady):
            self.__ChMode =ChMode
            self.getRawData()
    
    def getRawData(self):
        data=0
        if self.__Status&Status_OutReady:
            self.__Status&=~Status_OutReady
            for i in range(self.__ChMode):
                self.__PinSCK.value(1)
                sleep_us(2)
                if i<24: data=(data<<1)|self.__PinDOUT.value()
                self.__PinSCK.value(0)
                sleep_us(2)
            if data&0x800000: data=(data&0x7FFFFF)-0x800000
            #print(data)
            self.__PinDOUT.irq(trigger=Pin.IRQ_FALLING,handler=self.PinDOUT_IRQHandler)
        return data

    def updateADC(self, t):
        if self.__Status&Status_OutReady:
            tmp=self.getRawData()
            if tmp!=8388607:
                if self.__dataI<11:
                    self.__dataY[self.__dataI]=tmp
                    self.__dataI+=1
                else:
                    if self.__Check==1:
                        backup=self.__dataY.pop()
                        self.__dataY.append(tmp)
                        (a, b, e)=self.LinearReg(self.__dataX, self.__dataY)
                        if e<500:
                            (self.__LinRegA, self.__LinRegB, self.__LinRegE)=(a, b, e)
                            print("Corrected: remove %d"%(backup))
                        else:
                            self.__dataY.pop(0)
                            self.__dataY[-1]=backup
                            self.__dataY.append(tmp)
                            (self.__LinRegA, self.__LinRegB, self.__LinRegE)=self.LinearReg(self.__dataX, self.__dataY)
                        self.MeanValue=self.Average(self.__dataY)
                        self.LinRegVal=self.__LinRegB
                        self.__Check=0
                    else:
                        self.__dataY.pop(0)
                        self.__dataY.append(tmp)
                        (self.__LinRegA, self.__LinRegB, self.__LinRegE)=self.LinearReg(self.__dataX, self.__dataY)
                        self.MeanValue=self.Average(self.__dataY)
                        self.LinRegVal=self.__LinRegB
                        if self.__LinRegE>10000: self.__Check=1
                    if self.__LinRegE<250: self.ValStable=1
                    else: self.ValStable=0
    
    def startReadADC(self, state=-1, Freq=2):
        if (self.__Status&MaskCanPeriodicRead)==MaskCanPeriodicRead:
            if state==1 and (self.__Status&Status_PeriodicRead)==0x00 and (Freq>0 and Freq<=2):
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
        ADC=HX711(SCK=5, DOUT=4, ChMode=ChAx128, TimerPort=Tim)
        sleep(0.5)
        ADC.PowerOn()
        sleep(0.1)
        if ADC.startReadADC(1,2):
            while True:
                print(ADC.MeanValue, ADC.LinRegVal, ADC.ValStable)
                sleep(0.5)
    except KeyboardInterrupt:
        if ADC.__Status&Status_PeriodicRead: ADC.startReadADC(0)
        if ADC.__Status&Status_PowerOn: ADC.PowerOff()
        machine.reset()
        pass
    except:
        pass
    finally:
        pass
        
