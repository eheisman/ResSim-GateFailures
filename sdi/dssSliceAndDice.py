# EVAN HEISMAN, NWW
# November 2015
# SliceAndDice.py
# Used to create synthetic year files required by the FRA hydrologic sampler
# These are the files stored in $WATERSHED/shared/fra/CRT_(Forecasts|Inflows)_$SYNTHETIC_NAME.dss
# Input is a CSV file.
# Columns:
#   IN_FILE - file that data is read in from
#   OUT_FILE - file that output is written to
#   WATERYEAR - Water years to read, may list single year (e.g. 1948) or a range (e.g. 1929-1948) 
#   OFFSET - Move output by this string.
#            See HecMath.shiftInTime in DSSVue Manual, Chapter 8: Scripting
#   PATH_FILTER - filters input pathnames to only those that match this filter.
#                 See getCatalogedPathnames in DSSVue Manual, Chapter 8: Scripting
#   FPART_REPLACE
#   SKIP
#   COMMENT
#   All other columns are ignored.
#
# Run with execfile jython interpreter or paste into a DSSVue script.
# >>> execfile("D:/crt/hydrology/scripts/dssSliceAndDice.py")

from __future__ import with_statement
from hec.heclib.dss import HecDss
from hec.hecmath import TimeSeriesMath
from hec.hecmath import HecMathException
from csv import DictReader

def formatTimeString(wy, startTime="0001"):
    startWY = wy
    endWY = wy
    if "-" in str(wy):
        startWY, endWY = wy.split("-")
    return ("01Oct%d %s" % ((int(startWY)-1), startTime), "30Sep%d 2400" % int(endWY))

def tscToHecMath(tsc):
    hm = TimeSeriesMath()
    hm.setData(tsc)
    return hm

def copyBlock(inFilename, outFilename, WY, paths, newFPart=None, offset=None):
    outFile = HecDss.open(outFilename)
    #print(sd, ed)
    inFile = HecDss.open(inFilename)
    for path in paths:
        pathParts = path.split("/")[1:-1]
        startTime = "0001" # 0001 to make sure we capture the first value of the forecast OBSV paths.
        if pathParts[4].upper() == "1HOUR":   # If record is hourly, don't start until
            startTime = "2400"				  # 2400 of the first day.
        sd, ed = formatTimeString(WY, startTime)
        try:
          inFile.setTimeWindow("%s %s" % (sd, ed))
          data = TimeSeriesMath(inFile.get(path, True))
        except HecMathException:
          msg = "Unable to read HecMath object %s from file %s for %s to %s" % (path, inFilename, sd, ed)
          print(msg)
          with open(inFilename + ".log", 'a') as logFile:
            logFile.write(msg + "\n")
          continue
        if data is None:
            continue
        if newFPart:
            data.setVersion(newFPart)
            #data.fullName = replacePart(data.fullName, "F", newFPart)
        if offset and offset != "":
            #dataHM = TimeSeriesMath()
            #dataHM.setData(data)
            data = data.shiftInTime(offset)
            #data = dataHM.getData()
        sp =  simplePaths([data.getData().fullName])[0] 
        if not (newFPart is None or newFPart.strip() == ""): #sp in simplePaths(outFile.getCatalogedPathnames()):
            #insertDataset = tscToHecMath(outFile.get(sp, True))
            data.setVersion(newFPart) #"%s_%s" % (WY, newFPart))
        outFile.write(data)
    inFile.done()
    outFile.close()


# def expandWYs(wys):
    # newList = []
    # for WY in wys:
        # #if "-" in WY:
        # #    #startWY, endWY = WY.split("-")
        # #    #newList += range(int(startWY.strip()), int(endWY.strip())+1)
        # #    newList += WY
        # #else:
        # #    newList += int(WY)
    # return newList

def replacePart(p, part, newValue=""):
    p = p.split("/")
    p[" ABCDEF".find(part.upper())] = newValue
    p = "/".join(p)
    return p
            
def simplePaths(paths):
    return list(set([replacePart(p, "D") for p in paths]))

CONFIG_FILENAME = r"D:\HEC_Support\ICA_modeling\NBP_oca_2021-07-21_GateFailureScript\sdi\sliceAndDicePaths.csv"
with open(CONFIG_FILENAME, 'r') as configFile:
    inFilename = ""
    outFilename = ""
    wyString = ""
    WYs = None
    newFPart = None
    offset = None
    pathFilter = "NONE"
    for configLine in DictReader(configFile):
        if configLine["SKIP"].strip() != "":
            continue
        if configLine["IN_FILE"].strip() != inFilename and configLine["IN_FILE"].strip() != "":
            inFilename = configLine["IN_FILE"].strip()
        if configLine["OUT_FILE"].strip() != outFilename and configLine["OUT_FILE"].strip() != "":
            outFilename = configLine["OUT_FILE"].strip()
        if configLine["WATERYEARS"].strip() != wyString and configLine["WATERYEARS"].strip() != "":
            wyString = configLine["WATERYEARS"].strip()
            WYs = [wy.strip() for wy in wyString.split(",")]
        if configLine["OFFSET"].strip() != offset and configLine["OFFSET"].strip() != "":
            offset = configLine["OFFSET"].strip()
            if offset in ["0", ""]:
                offset = None
        if configLine["FPART_REPLACE"].strip() != newFPart:
            newFPart = configLine["FPART_REPLACE"].strip()
        if configLine["PATH_FILTER"].strip() != pathFilter and configLine["PATH_FILTER"].strip() != "":
            pathFilter = configLine["PATH_FILTER"].strip()
        inFile = HecDss.open(inFilename)
        paths = inFile.getCatalogedPathnames()
        if pathFilter != "NONE":
            paths = simplePaths(inFile.getCatalogedPathnames(pathFilter))
        inFile.done()
        for wy in WYs:
            copyBlock(inFilename, outFilename, wy, paths, newFPart=newFPart, offset=offset)
