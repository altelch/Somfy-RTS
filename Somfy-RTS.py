#!/usr/bin/python
#-------------------------------------------------------------------------------
# Name:        Somfy-RTS.py (based on BitBucketConverter.py)
# Purpose:     Decode received 'B1' data.
#
# Author:      altelch / gerardovf
#
# Created:     28/01/2019
#-------------------------------------------------------------------------------

from optparse import OptionParser
import json
import pycurl
from sys import exit
from optparse import OptionParser
from StringIO import StringIO
from enum import IntEnum

def deobfuscate(frame):
  for i in range(6,0,-1):
    frame[i] = frame[i] ^ frame[i-1]
  print("Group       A       B       C       D       F               G                    ")
  print("Byte:       0H      0L      1H      1L      2       3       4       6       7    ")
  print("        +-------+-------+-------+-------+-------+-------+-------+-------+-------+")
  print("        ! 0xA   + R-KEY ! C M D ! C K S !  Rollingcode  ! Remote Handheld Addr. !")
  print("        !"),
  print hex((frame[0]>>4) & 0xf), "  + ", hex((frame[0] & 0xf)), " ! ", hex((frame[1]>>4 & 0xf)), " ! ", hex((frame[1] & 0xf)), " !    ", hex((frame[2]<<8) + frame[3]), "   !       ", hex((frame[4]<<16) + (frame[5]<<8) + frame[6]), "      !"
  print("        +-------+-------+-------+-------+MSB----+----LSB+LSB----+-------+----MSB+")

class ManchesterDecode:
  def init(self, nextBit, secondPulse):
    self.nextBit = nextBit
    self.secondPulse = secondPulse
    self.count = 0
    self.bitvec = ""

  def addShortPulse(self):
    if self.secondPulse:
       #print(self.nextBit),
       self.bitvec=self.bitvec+str(self.nextBit)
       self.count=self.count+1
       self.secondPulse=False
    else:
       self.secondPulse=True

  def addLongPulse(self):
    if not self.secondPulse:
      return false
    #print(self.nextBit),
    self.bitvec=self.bitvec+str(self.nextBit)
    self.nextBit = self.nextBit ^ 1
    self.count=self.count+1
    return True

  def get_bitvector(self):
    #print(self.bitvec)
    return int(self.bitvec,base=2)

class States(IntEnum):
  ST_UNKNOWN  = 0
  ST_HW_SYNC1 = 1
  ST_HW_SYNC2 = 2
  ST_HW_SYNC3 = 3
  ST_HW_SYNC4 = 4
  ST_SW_SYNC1 = 5
  ST_SW_SYNC2 = 6
  ST_PAYLOAD = 7
  ST_DONE = 8

def getInputStr():
    #auxStr = '18:30:23 MQT: /sonoff/bridge/RESULT = {"RfRaw":{"Data":"AA B1 05 02FD 0E48 14CF 05E6 503C 000000030102010103010103010101010101010104 55"}}'
    auxStr = raw_input("Enter B1 line: ")
    iPos = auxStr.find('"}}')
    if (iPos > 0):
        # Strip 'extra' info
        #auxStr = auxStr.lower()
        myfind = '"Data":"'
        iPos1 = auxStr.find(myfind)
        if iPos > 0:
            auxStr = auxStr[iPos1+len(myfind):iPos]
#           print(auxStr)
        else:
            auxStr = ""
    return auxStr

def main(szInpStr):
    #print("Input: %s" % szInpStr) #HK
    listOfElem = szInpStr.split()
    #print("ListofElem: %s" % listOfElem) #HK
    iNbrOfBuckets = int(listOfElem[2])
    #print("NumBuckets: %d" % iNbrOfBuckets) #HK
    # Start packing
    state = States.ST_UNKNOWN
    pulse = {}
    szOutAux = ""
    szOutAux += listOfElem[2]
    strHex = ""
    szOutAux += strHex
    bitvec = "0b"
    for i in range(0, iNbrOfBuckets):
        strHex = listOfElem[i + 3]
        iValue = int(strHex, 16) #HK
        if iValue > 448 and iValue < 832:
          pulse[i]="Short"
        if iValue > 896 and iValue < 1664:
          pulse[i]="Long"
        if iValue > 1792 and iValue < 3328:
          pulse[i]="HWsync"
        if iValue > 3136 and iValue < 5824:
          pulse[i]="SWsync"
        if iValue > 25000:
          pulse[i]="InterFrameGap"
        print("Bucket %d: %s (%d)" % (i, pulse[i], iValue)) #HK
        szOutAux += strHex
    strHex = listOfElem[iNbrOfBuckets + 3]
    szOutAux += strHex
    szDataStr = strHex
    szOutAux += listOfElem[iNbrOfBuckets + 4]
    iLength = len(szDataStr)
    strNew = ""
    decode=ManchesterDecode()
    for i in range(0, iLength):
        pos = i
        strHex = szDataStr[pos:pos+1]
        strNew += strHex
        strNew += " "
        #print(strHex) #HK
    if(options.debug):
        print("Data: %s" % (strNew))
    listOfElem = strNew.split()
    iNbrOfNibbles = len(listOfElem)
    for i in range(0,iNbrOfNibbles):
      if(options.debug):
         print pulse[int(listOfElem[i])]
      if pulse[int(listOfElem[i])] is "HWsync":
         #print "HWsync"
         state=state+1
         if state > States.ST_HW_SYNC4:
           state=States.ST_UNKNOWN
      elif pulse[int(listOfElem[i])] is "SWsync" and state == States.ST_HW_SYNC4:
         #print "SWsync"
         state=States.ST_SW_SYNC2
      elif pulse[int(listOfElem[i])] is "Long" and state == States.ST_SW_SYNC2:
         #print "Sync Long",
         state=States.ST_PAYLOAD
         decode.init(1,True)
      elif pulse[int(listOfElem[i])] is "Short" and state == States.ST_SW_SYNC2:
         #print "Sync Short",
         state=States.ST_PAYLOAD
         decode.init(0,False)
      elif state == States.ST_PAYLOAD:
        if pulse[int(listOfElem[i])] is "Short":
          #print "Short",
          decode.addShortPulse()
        elif pulse[int(listOfElem[i])] is "Long":
          #print "Long",
          if not decode.addLongPulse():
            state = States.ST_UNKNOWN
        elif pulse[int(listOfElem[i])] is "InterFrameGap":
          #print "InterFrameGap"
          if decode.count==55:
            decode.bitvec=decode.bitvec+str(decode.nextBit)
#         else:
#           print("") 
          state = States.ST_DONE
        else:
          state = States.ST_UNKNOWN
      else:
           state=States.ST_UNKNOWN
      if(options.debug):
        print("%d: %s" % (i,States(state)))

    print(bin(decode.get_bitvector()))
    print(hex(decode.get_bitvector()))
    number = decode.get_bitvector()
    frame = {}
    frame[0] = (number>>48) & 0xff
    frame[1] = (number>>40) & 0xff
    frame[2] = (number>>32) & 0xff
    frame[3] = (number>>24) & 0xff
    frame[4] = (number>>16) & 0xff
    frame[5] = (number>>8) & 0xff
    frame[6] = number & 0xff
    deobfuscate(frame)

usage = "usage: %prog [options]"
parser = OptionParser(usage=usage, version="%prog 0.2")
parser.add_option("-d", "--debug", action="store_true",
                  dest="debug", default=False, help="show debug info")
parser.add_option("-v", "--verbose", action="store_true",
                  dest="verbose", default=False, help="show more detailed info")
(options, args) = parser.parse_args()

# In program command line put two values (received Raw between '"' and desired repeats)
# Example: "AA B1 05 12DE 05C8 02D5 0172 23A0 0123322323233232323223323232323223233232232332233223233232323232233232322323232334 55" 20
if __name__ == '__main__':
    '''
    print(len(args))
    if len(args) < 1:
        #parser.error("incorrect number of arguments. Use -h or --help")
        print(parser.print_help())
        exit(1)
    '''
    while(True):
        strInput = getInputStr()
        if (len(strInput) > 0):
            main(strInput)
        else:
            break
    #print(parser.print_help())
