# Generalized gate failure rule

# User README:
# Configure this rule as a scripted rule that 'operates from' the outlet that matches the column name in gates.csv
# This should be something like "DAM NAME-OUTLET NAME"
# To work correctly, this MUST the highest priority rule in every zone.
# If there are several gate outages at a dam, the order should not matter as long as they are all high priority.

# required imports to create the OpValue return object.
from hec.rss.model import OpValue
from hec.rss.model import OpRule
from hec.script import Constants, HecDss
from hec.heclib.util import HecTime

# testing constants
TEST_N_GATES = 1.
# implemented ramping rates to help smooth hydrograph for HEC-RAS model
# TODO: Move these to config.csv, but how?  This might be a setting per dam.
RAMPING = False
RAMPING_TIMESTEPS = 8.0 # timesteps to failure
#
# initialization function. optional.
#
# set up tables and other things that only need to be performed once during
# the compute.
#
# currentRule is the rule that holds this script
# network is the ResSim network
#
#
def initRuleScript(currentRule, network):
    # return Constants.TRUE if the initialization is successful
    # and Constants.FALSE if it failed.  Returning Constants.FALSE
    # will halt the compute.
    return Constants.TRUE
    
def getFailureTimeFromTS(inputTSC, criteriaFunc):
    """
    @param inputTSC - timeseries container
    @param criteriaFunc - function that evalutes list of values and returns a value to match, typically use python's max function
    @return HecTime when timeseries matches criteriaFunc's value
    """
    match = criteriaFunc(inputTSC.values)
    for t,v in zip(inputTSC.times, inputTSC.values):
        # return first time that matches criteria function
        if v == match:
            tOut = HecTime()
            tOut.set(t)
            return tOut

# runRuleScript() is the entry point that is called during the
# compute.
#
# currentRule is the rule that holds this script
# network is the ResSim network
# currentRuntimestep is the current Run Time Step
def runRuleScript(currentRule, network, currentRuntimestep):
    ruleName = currentRule.getName()
    resv = currentRule.getReservoirElement()
    resvName = resv.getName()
    controller = currentRule.getController()
    controllerName = controller.getDisplayName()
    releaseElement = controller.getReleaseElement() # aka gates
    releaseElementName = releaseElement.getName()

    gateID = "-".join((resvName, releaseElementName)).upper()
    gateControlSV = network.getStateVariable("GateControl")
    outages = gateControlSV.varGet("outages")

    if not gateID in outages.keys():
        return None # do nothing, this gate doesn't have an outage
    outage = outages[gateID]
    gateState = outage["STATE"]
    gateMode = outage["MODE"]
    gateFraction = outage["FRACTION"]
    # outage is dictionary (or Namedtuple) with `state` and `fraction`

    if not currentRule.varExists("init"):
        network.printMessage("%s rule operates %s/%s as %s at %2.1f%%" % (ruleName, resvName, releaseElementName, gateState, gateFraction*100.))
        currentRule.varPut("init", True)

    # determine the trigger model F-part, either use something from this model if blank, otherwise a similar model in the ResSim.dss file
    run = network.getRssRun()
    failureFPart = run.getOutputFPart()
    if gateControlSV.varGet("outageTriggerModel").strip() != "":
        failureFPart = "BASELINE--0"
    
	# check time of failure based on unreg.
    # if timestep is before failure time, return none    
    if not currentRule.varExists("failureTimestep"): # compute once, unreg flow unchanged during compute
        if gateMode.upper() == "UNREG":
            # get unreg inflow from output file
            usElement = resv.getUpstreamNode().getUpstreamElement()
            usName = usElement.getName()

            run = network.getRssRun()
            if not run.getComputeUnReg():
                network.printErrorMessage("Unreg compute not enabled, script will fail.  Please turn `compute unreg` on in the alternative editor.")
            outFile = HecDss.open(run.getDSSOutputFile())
            rtw = currentRuntimestep.getRunTimeWindow()
            # create unreg path as "//<element name>/FLOW-UNREG//<timestep>/<model fpart>/"
            interval = rtw.getTimeStepString(0) # zero for no space
            unregPath = "/".join(["", "", usName, "FLOW-UNREG", "", interval, failureFPart])
            unregTS = outFile.read(unregPath, rtw.getTimeWindowString()).getData()
            outFile.done()
            # get time of failure
            failureTime = getFailureTimeFromTS(unregTS, max)
            failureTimestep = rtw.getStepAtTime(failureTime)
            #network.printWarningMessage("failure for %s will occur at %s " % (gateID, failureTime.toString()))
            currentRule.varPut("failureTimestep", failureTimestep)
        elif gateMode.upper() == "ELEV":
            # get unreg inflow from output file
            poolName = resv.getName() + "-POOL"

            run = network.getRssRun()
            #if not run.getComputeUnReg():
            #    network.printErrorMessage("Unreg compute not enabled, script will fail.  Please turn `compute unreg` on in the alternative editor.")
            outFile = HecDss.open(run.getDSSOutputFile())
            rtw = currentRuntimestep.getRunTimeWindow()
            # create unreg path as "//<element name>/FLOW-UNREG//<timestep>/<model fpart>/"
            interval = rtw.getTimeStepString(0) # zero for no space
            unregPath = "/".join(["", "", poolName, "ELEV", "", interval, failureFPart])
            unregTS = outFile.read(unregPath, rtw.getTimeWindowString()).getData()
            outFile.done()
            # get time of failure
            failureTime = getFailureTimeFromTS(unregTS, max)
            failureTimestep = rtw.getStepAtTime(failureTime)
            #network.printWarningMessage("failure for %s will occur at %s " % (gateID, failureTime.toString()))
            currentRule.varPut("failureTimestep", failureTimestep)
    
    # get failure time and do nothing if before failure time
    if currentRule.varExists("failureTimestep") and currentRuntimestep.getStep() < currentRule.varGet("failureTimestep"):
        #network.printErrorMessage("failure has not yet occured on %s" % currentRuntimestep.dateTimeString())
        opValue = OpValue()
        opValue.init(OpRule.RULETYPE_MIN, 0) # do nothing
        return opValue # failure point not reached


    #elev = resv.getEffectiveElev(currentRuntimestep)
    #AdjustableFlow.getCurrentCapacity()
    gateMax = controller.getAdjustableParameter().getMaxValue()

    # create new Operation Value (OpValue) to return
    opValue = OpValue()
    # set type and value for OpValue
    #  type is one of:
    #  OpRule.RULETYPE_MAX  - maximum flow
    #  OpRule.RULETYPE_MIN  - minimum flow
    #  OpRule.RULETYPE_SPEC - specified flow
    #
    # considered using SPEC instead of MIN for STUCK_OPEN and MAX for STUCK_SHUT, but this will work better?
    # SPEC would not work if other gate rules are in effect, e.g. "open all the gates, even the stuck open one."
    opType = OpRule.RULETYPE_SPEC 
    if gateState == "OPEN":
        opType = OpRule.RULETYPE_MIN
        # minimum uses fraction as is, as this is the minimum of the limit that must be passed.
    elif gateState == "SHUT":
        opType = OpRule.RULETYPE_MAX
        gateFraction = 1-gateFraction # invert for stuck shut so that fraction is number that can't be used
    else:
        pass
        #opType = OpRule.RULETYPE_SPEC

    gradualFailureCoef = 1
    if RAMPING:
        gradualFailureCoef = (currentRuntimestep.getStep() - currentRule.varGet("failureTimestep"))/RAMPING_TIMESTEPS
        gradualFailureCoef = min(max(gradualFailureCoef,0),1)

    opValue.init(opType, gateFraction*gateMax*gradualFailureCoef)
    # return the Operation Value.
    # return "None" to have no effect on the compute
    return opValue