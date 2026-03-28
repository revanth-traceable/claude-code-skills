import base64
import logging
import json
import re
import jsonpath_ng as jq
import sys
import io
import collections


class FIFOIO(io.TextIOBase):
    def __init__(self, size, *args):
        self.maxsize = size
        io.TextIOBase.__init__(self, *args)
        self.deque = collections.deque()

    def getvalue(self):
        res = ''.join(self.deque)
        # now we flush the buffer
        self.deque = collections.deque()
        return res

    def write(self, x):
        self.deque.append(x)
        self.shrink()

    def shrink(self):
        if self.maxsize is None:
            return
        size = sum(len(x) for x in self.deque)
        while size > self.maxsize:
            x = self.deque.popleft()
            size -= len(x)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logdata = []
# we store all logs in logdata
log_capture_string = FIFOIO(10000)
log.addHandler(logging.StreamHandler(log_capture_string))

class UserAttribution:
    attributes: dict
    def __init__(self, data: dict, attributes: dict):
        self.attributes = attributes
        self.output = {}
        self.run_projector(data)

    def run_projector(self, data: dict, value: str = ""):
        projector = data.get("projector", None)
        if not projector:
            raise Exception("Projector not found")
        # we need the first key to know the projector
        projector_name = list(projector.keys())[0]
        log.log(logging.INFO, "Running projector %s" % projector_name)
        projector = projector[projector_name]
        if projector_name == "base64Projector":
            return self.run_base64projector(projector, value)
        elif projector_name == "attributeProjector":
            return self.run_attribute_projector(projector, value)
        elif projector_name == "regexCaptureGroupProjector":
            return self.run_regex_capture_group_projector(projector, value)
        elif projector_name == "valueProjector":
            return self.run_value_projector(projector, value)
        elif projector_name == "noOpProjector":
            return value
        elif projector_name == "conditionalProjector":
            return self.run_conditional_projector(projector, value)
        elif projector_name == "jsonProjector":
            return self.run_json_projector(projector, value)
        elif projector_name == "jwtProjector":
            return self.run_jwt_projector(projector, value)
        else:
            raise Exception("Projector %s not found" % projector_name)

    def run_attribute_rule(self, attribute_rule: dict, value: str = ""):
        if not attribute_rule:
            raise Exception("Attribute rule not found")
        if "projector" in attribute_rule:
            return self.run_projector(attribute_rule, value)
        elif "initialActions" in attribute_rule:
            return self.run_initial_actions(attribute_rule["initialActions"], value)
        else:
            raise Exception("Attribute rule not found")

    def run_initial_actions(self, ia: list, value: str = ""):
        for action in ia:
            keys = list(action.keys())
            if "attributeAddition" in keys:
                key = action["attributeAddition"]["attributeKey"]
                vpr = action["attributeAddition"]["valueProjectionRule"]
                log.log(logging.INFO, "Running attribute addition for key %s" % key)
                self.output[key] = self.run_projector(vpr, value)
            elif "attributeArrayAppend" in keys:
                key = action["attributeArrayAppend"]["attributeKey"]
                vpr = action["attributeArrayAppend"]["valueProjectionRule"]
                log.log(logging.INFO, "Running attribute array append for key %s" % key)
                val = self.run_projector(vpr, value)
                if key not in self.output:
                    self.output[key] = []
                if not isinstance(self.output[key], list):
                    self.output[key] = [self.output[key]]
                self.output[key].append(val)

    def run_value_projector(self, projector: dict, value: str = ""):
        value = projector.get("value", "")
        log.log(logging.INFO, "Running value projector with value %s" % value)
        return value

    def run_json_projector(self, projector: dict, value: str = ""):
        try:
            decoded = json.loads(value)
        except:
            log.log(logging.INFO, "JSON decode failed")
            decoded = {}
        projector = projector["jsonPathRule"]
        key = projector["key"]
        query = jq.parse(key)
        res = query.find(decoded)
        if len(res) == 0:
            value = ""
            log.log(logging.INFO, "JQ result not found")
        else:
            value = res[0].value
            log.log(logging.INFO, "Got JQ result %s" % value)
        return self.run_attribute_rule(projector.get("attributeRule", None), value)

    def run_conditional_projector(self, projector: dict, value: str = ""):
        keys = list(projector.keys())
        if "predicate" in keys:
            attr = projector["predicate"]["attributePredicate"]
            np = attr["namePredicate"]
            npop = np["operator"]
            npval = np["value"]
            attribute = self.attributes.get(npval, "")
            log.info("Running conditional projector predicate with value %s" % attribute)
            vp = attr["valuePredicate"]
            vpval = vp["value"]
            vpop = vp["operator"]
            if vpop == "COMPARISON_OPERATOR_MATCHES_REGEX":
                regex = re.compile(vpval)
                match = regex.search(attribute)
                if not match:
                    log.log(logging.INFO, "Conditional %s Regex did not match %s" %
                            (vpval, attribute))
                else:
                    log.log(logging.INFO, "Conditional Regex matched %s" % attribute)
                    return self.run_attribute_rule(projector.get("attributeRule", None), value)
            else:
                raise Exception("Operator %s not found" % vpop)

    def run_jwt_projector(self, projector: dict, value: str = ""):
        spl = value.split(".")
        if len(spl) != 3:
            log.log(logging.INFO, "JWT not found, skipping")
            return
        if "claimRule" in projector:
            claims = json.loads(base64.b64decode(
                spl[1] + "=" * ((4 - len(spl[1]) % 4) % 4)).decode("utf-8"))
            for key, value in claims.items():
                log.log(logging.INFO, "Running JWT claim %s->%s" % (key, value))
            key = projector["claimRule"]["key"]
            value = claims.get(key, "")
            log.log(logging.INFO, "Got JWT claim with value %s" % value)
            return self.run_attribute_rule(
                projector["claimRule"].get("attributeRule", None), value)
        elif "headerRule" in projector:
            header = json.loads(base64.b64decode(spl[0]).decode("utf-8"))
            key = projector["headerRule"]["key"]
            value = header.get(key, "")
            log.log(logging.INFO, "Got JWT header with value %s" % value)
            return self.run_attribute_rule(
                projector["headerRule"].get("attributeRule", None), value)


    def run_regex_capture_group_projector(self, projector: dict, value: str = ""):
        expr = projector.get("regexCaptureGroup", None)
        if not expr:
            raise Exception("Regex not found")
        if "(?i)" in expr:
            expr = expr.replace("(?i)", "")
            regex = re.compile(expr, re.IGNORECASE)
        else:
            regex = re.compile(expr)
        if not value:
            value = ""
        match = regex.search(value)
        if not match:
            log.log(logging.INFO, "%s Regex did not match %s" %
                    (expr, value))
            value = ""
        else:
            value = match.group(1)
            log.log(logging.INFO, "Regex matched %s" % value)
        return self.run_attribute_rule(projector.get("attributeRule", None), value)

    def run_base64projector(self, projector: dict, value: str = ""):
        try:
            value = base64.b64decode(value).decode("utf-8")
            log.log(logging.INFO, "Running base64 projector with value %s" % value)
        except:
            log.log(logging.INFO, "Base64 decode failed")
        return self.run_attribute_rule(projector.get("attributeRule", None), value)

    def run_attribute_projector(self, projector: dict, value: str = ""):
        key = projector.get("attributeKey", None)
        value = self.attributes.get(key, "")
        log.log(logging.INFO, "Running attribute projector for key %s with value %s" % (
            key, value))
        return self.run_attribute_rule(projector.get("attributeRule", None), value)
