from hec.script import Constants
from csv import DictReader
import os.path

## READ ME USER
# This script goes in a state variable that MUST be called "GateControl" for the rules to find it.
# The script must be placed in the inititalization tab.  The main and cleanup scripts can be left as-is or blank.


# Steps in this script
# 1) Read $watershed/shared/gates/<analysis_period>_config.csv using "KEY" "VALUE" "COMMENT" (optional) fields
# 2) Read $watershed/shared/gates/<analysis period>_gates.csv
# 	parse into gate configurations based on rows
#		column headers = eventID, state, "<dam name>/<gate name>" per gate
#		rows:
# 			blank - no restrictions
#			"OPEN" - stuck open - min release = gate capacity at prev elev
#			"SHUT" - stuck shut - max release = 0
#			future: percentage e.g. "50%" - stuck at 50% of gate capacity at elev, 100% is equivalent to OPEN; 0% is equivalent to SHUT
# 	eventID column determined by:
# 	- Ensemble ID in f:part # good for ResSim ensemble standalone testing OR randomized WAT
#	- WAT lifecycle number *** this one is good for SDI computes
#   - ensemble ID by lifecycle # good for randomized process (e.g. with Hydrologic Sampler)
#	- timeseries - number in timeseries matches current condition - variable gate conditions by timestep

# this State Variable is responsible for assigning the current condition and making accessible to other scripts
# local variables:
#	gateCondition - dictionary of current gate configuration from row identified by this SV
#
#	This SV works along side a template rule (e.g. same for every outlet)
# 	Template rule looks at dam/gate name to determine which condition to read and set release.
# 	Template rule(s) should be highest priority rule(s) at reservior.
##
# variables that are passed to this script during the compute initialization:
# 	currentVariable - the StateVariable that holds this script
# 	network - the ResSim network
#
# Alternative ideas:
# - use RssRun.getReleaseOverrides() and set them prior to compute - no rules required!  
#       Not going this route as you can only override capacity as a factor.  
#       Would need to release override by gate?  Works good, does not allow for capacity calcs. (see ReleaseOverrideTests.py)

def initStateVariable(currentVariable, network):
    # return Constants.TRUE if the initialization is successful and Constants.FALSE if it failed.  
    # Returning Constants.FALSE will halt the compute.

    # read configuration file
    configFilename = network.makeAbsolutePathFromWatershed(os.path.join("shared", "gates", "config.csv"))
    configFile = open(configFilename, 'r')
    config = dict()
    for row in DictReader(configFile):
        v = row["VALUE"]
        k = row["KEY"]
        config[k] = v 
        network.printMessage("gate control config: %s: %s"% (k,v))
    configFile.close()

    # read outages file
    outagesFile = "gates.csv"
    allOutages = dict() # dict to allow alpha-numeric event ids
    if "OUTAGES_FILE" in config.keys():
        outagesFile = config["OUTAGES_FILE"]
    outagesFile = open(network.makeAbsolutePathFromWatershed(os.path.join("shared", "gates", outagesFile)))
    firstRow = None
    for row in DictReader(outagesFile):
        try: # to convert to int
            eventID = int(row["EVENTID"])
        except ValueError, e:
            # just use as a string
            eventID = row["EVENTID"]
        allOutages[eventID] = row
        if firstRow is None:
            firstRow = row
    outagesFile.close()

    # create default case if needed
    if not allOutages.has_key(0):
        allOutages[0] = firstRow

    
    # metadata about run
    run = network.getRssRun()
    watCompute = False
    simFileName = str(run.getDSSOutputFile())
    network.printMessage(simFileName)
    # initialize all of these for a default case in ResSim only
    frmCompute = False
    lc = 0
    realization = 0
    event = 0
    collectionID = 0
    wat_alt = ""
    analysis_period = ""

    # this whole block of code should go away in WAT 1.1 / ResSim 3.5
    fPart = run.getOutputFPart()
    if "|" in fPart:
    	cid, rest = fPart.split("|")
    	collectionID = int(cid.split(":")[-1]) 
    if "runs" in simFileName: # WAT compute old method
        watCompute = True
        parts = simFileName.split(os.path.sep)
        # sim file
        simFile = parts[-1]
        # lifecycle
        if "lifecycle" in parts[-2] > 0:
            frmCompute = True
            lc = int(parts[-2].replace("lifecycle ", ""))
        # event
        # get fpart
        if frmCompute:
            wat_alt, analysis_period, model_alt = rest.split(":")
            event = collectionID
            if config.has_key("EVENTS_IN_LC"):
                event = collectionID + (lc-1)*int(config["EVENTS_IN_LC"])
    
    # determine outage ID
    outageID = 0 # default case
    outageSource = str(config["OUTAGE_SOURCE"].upper().strip())
    network.printMessage("using outage source %s" % repr(outageSource)) 
    if outageSource == "EVENT": # == to compare str against unicode from file
        if watCompute and frmCompute: #watCompute.isFrmCompute():
            #watComputeOptions = run.getAdditionalComputeOptions() 
            # wat compute options -> event ID to determine outages
            outageID = event #watComputeOptions.getCurrentEventNumber()
        else:
            # ResSim standalone ensemble compute
            network.printWarningMessage("ResSim compute, no WAT event found.")
            outageID = collectionID # default outage
    elif outageSource == "LIFECYCLE":
        # wat compute options -> lifecycle ID
        if watCompute and frmCompute: #watComputFe.isrmCompute()::
            #watComputeOptions = run.getAdditionalComputeOptions() 
            outageID = lc #watComputeOptions.getCurrentLifecycleNumber()
        else:
            network.printWarningMessage("ResSim compute, no WAT lifecycle found.")
            outageID = 0
    elif outageSource == "RESSIM_ALT":
        # use ResSim alternative name
        outageID = run.getAlternative().getDisplayName().split(":")[-1]
    elif outageSource == "WAT_ALT":
        # use WAT alternative name
        if watCompute:
            #watComputeOptions = run.getAdditionalComputeOptions() 
            outageID = wat_alt #watComputeOptions.getSimulationName().split("-")[0] # get from sim name
        else:
            network.printWarningMessage("ResSim compute, no WAT alternative name found.")
    elif outageSource == "TIMESERIES":
        # do nothing now, main script can vary current outage
        # not currently working
        network.printWarningMessage("TIMESERIES outage source not implemented")
    else:
        network.printWarningMessage("Not valid outage source: %s\n\tUsing first row only." % outageSource)

    outages = allOutages[outageID]
    if outageID == 0: outageID = "default (0) outage"
    network.printMessage("using outage '%s': %s" % (outageID, str(outages)))

    # parse into gate outages for rules
    gateOutages = {}
    state = outages["FAILURE_STATE"]
    mode = outages["FAILURE_MODE"]
    for gateID, val in outages.items():
        if gateID.upper() in ("FAILURE_STATE", "FAILURE_MODE", "EVENTID", "COMMENT"): continue
        if val is None or len(val) == 0: continue
        # create outage dict (formerly named tuple... jython error)
        outage = dict()
        outage["STATE"] = state
        outage["MODE"] = mode
        outage["FRACTION"] = float(outages[gateID.upper()])
        gateOutages[gateID.upper()] = outage
        
    currentVariable.varPut("outageSource", outageSource)
    currentVariable.varPut("outages", gateOutages)
    currentVariable.varPut("allOutages", allOutages)
    # currentVariable.varPut("outageTrigger", config["OUTAGE_TRIGGER"].upper())
    currentVariable.varPut("outageTriggerModel", config["TRIGGER_MODEL"].upper())

    return Constants.TRUE