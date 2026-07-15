"""
Build the Diagnosis Reference Table (v3) from the supervisor-provided
ICD-10-AM mapping. Output: diagnosis_ref.csv with three columns:
  diagnosis_code | diagnosis_description | diagnosis_group

15 groups. Ranges like F19.0-F19.9 are expanded; 'F18.0 F18.9' is treated
as the range F18.0-F18.9. Code descriptions are generated from standard
ICD-10 category wording; 5th-character (ICD-10-AM) subdivisions are labelled
generically — replace with the ACCD ICD-10-AM tabular list wording for
production.

Run:  python build_diagnosis_ref.py
"""

import pandas as pd

F1X_SUBSTANCE = {
    "F10": "alcohol", "F11": "opioids", "F12": "cannabinoids",
    "F13": "sedatives or hypnotics", "F14": "cocaine",
    "F15": "other stimulants, including caffeine", "F16": "hallucinogens",
    "F18": "volatile solvents",
    "F19": "multiple drug use and use of other psychoactive substances",
}
F1X_QUALIFIER = {
    "0": "acute intoxication", "1": "harmful use", "2": "dependence syndrome",
    "3": "withdrawal state", "4": "withdrawal state with delirium",
    "5": "psychotic disorder", "6": "amnesic syndrome",
    "7": "residual and late-onset psychotic disorder",
    "8": "other mental and behavioural disorders",
    "9": "unspecified mental and behavioural disorder",
}
FIXED = {
    "E52": "Niacin deficiency [pellagra]",
    "G31.2": "Degeneration of nervous system due to alcohol",
    "G62.1": "Alcoholic polyneuropathy",
    "G72.1": "Alcoholic myopathy",
    "I42.6": "Alcoholic cardiomyopathy",
    "K29.2": "Alcoholic gastritis",
    "K70.0": "Alcoholic fatty liver",
    "K70.1": "Alcoholic hepatitis",
    "K70.2": "Alcoholic fibrosis and sclerosis of liver",
    "K70.3": "Alcoholic cirrhosis of liver",
    "K70.4": "Alcoholic hepatic failure",
    "K70.9": "Alcoholic liver disease, unspecified",
    "K85.2": "Alcohol-induced acute pancreatitis",
    "K85.3": "Drug-induced acute pancreatitis",
    "K86.0": "Alcohol-induced chronic pancreatitis",
    "T51.0": "Toxic effect of ethanol",
    "T51.1": "Toxic effect of methanol",
    "T51.2": "Toxic effect of 2-propanol",
    "T41.0": "Poisoning by inhaled anaesthetics",
    "T41.1": "Poisoning by intravenous anaesthetics",
    "T41.2": "Poisoning by other and unspecified general anaesthetics",
    "T50.7": "Poisoning by analeptics and opioid receptor antagonists",
    "T38.7": "Poisoning by androgens and anabolic congeners",
    "T40.0": "Poisoning by opium",
    "T40.1": "Poisoning by heroin",
    "T40.2": "Poisoning by other opioids",
    "T40.3": "Poisoning by methadone",
    "T40.4": "Poisoning by other synthetic narcotics",
    "T40.5": "Poisoning by cocaine",
    "T40.6": "Poisoning by other and unspecified narcotics",
    "T40.7": "Poisoning by cannabis (derivatives)",
    "T40.8": "Poisoning by lysergide [LSD]",
    "T40.9": "Poisoning by other and unspecified psychodysleptics [hallucinogens]",
    "T39.0": "Poisoning by salicylates",
    "T39.1": "Poisoning by 4-aminophenol derivatives",
    "T39.3": "Poisoning by other nonsteroidal anti-inflammatory drugs [NSAID]",
    "T39.4": "Poisoning by antirheumatics, not elsewhere classified",
    "T39.8": "Poisoning by other nonopioid analgesics and antipyretics, NEC",
    "T39.9": "Poisoning by nonopioid analgesic, antipyretic and antirheumatic, unspecified",
    "T42.3": "Poisoning by barbiturates",
    "T42.4": "Poisoning by benzodiazepines",
    "T42.5": "Poisoning by mixed antiepileptics, not elsewhere classified",
    "T42.6": "Poisoning by other antiepileptic and sedative-hypnotic drugs",
    "T42.7": "Poisoning by antiepileptic and sedative-hypnotic drugs, unspecified",
    "T43.0": "Poisoning by tricyclic and tetracyclic antidepressants",
    "T43.1": "Poisoning by monoamine-oxidase-inhibitor antidepressants",
    "T43.2": "Poisoning by other and unspecified antidepressants",
    "T43.3": "Poisoning by phenothiazine antipsychotics and neuroleptics",
    "T43.4": "Poisoning by butyrophenone and thioxanthene neuroleptics",
    "T43.5": "Poisoning by other and unspecified antipsychotics and neuroleptics",
    "T43.6": "Poisoning by psychostimulants with abuse potential",
    "T43.8": "Poisoning by other psychotropic drugs, not elsewhere classified",
    "T43.9": "Poisoning by psychotropic drug, unspecified",
    "F55.0": "Abuse of non-dependence-producing substances: antidepressants",
    "F55.2": "Abuse of non-dependence-producing substances: analgesics",
    "F55.5": "Abuse of non-dependence-producing substances: steroids or hormones",
    "X40": "Accidental poisoning by and exposure to nonopioid analgesics, antipyretics and antirheumatics",
    "X41": "Accidental poisoning by and exposure to antiepileptic, sedative-hypnotic, antiparkinsonism and psychotropic drugs, NEC",
    "X42": "Accidental poisoning by and exposure to narcotics and psychodysleptics [hallucinogens], NEC",
    "X43": "Accidental poisoning by and exposure to other drugs acting on the autonomic nervous system",
    "X44": "Accidental poisoning by and exposure to other and unspecified drugs, medicaments and biological substances",
    "X45": "Accidental poisoning by and exposure to alcohol",
    "X46": "Accidental poisoning by and exposure to organic solvents and halogenated hydrocarbons and their vapours",
    "X60": "Intentional self-poisoning by and exposure to nonopioid analgesics, antipyretics and antirheumatics",
    "X61": "Intentional self-poisoning by and exposure to antiepileptic, sedative-hypnotic, antiparkinsonism and psychotropic drugs, NEC",
    "X62": "Intentional self-poisoning by and exposure to narcotics and psychodysleptics [hallucinogens], NEC",
    "X63": "Intentional self-poisoning by and exposure to other drugs acting on the autonomic nervous system",
    "X64": "Intentional self-poisoning by and exposure to other and unspecified drugs, medicaments and biological substances",
    "X65": "Intentional self-poisoning by and exposure to alcohol",
    "X66": "Intentional self-poisoning by and exposure to organic solvents and halogenated hydrocarbons and their vapours",
}


def f1x_range(stem):                       # 'F12' -> F12.0 .. F12.9
    return [f"{stem}.{q}" for q in "0123456789"]


def f1x_am5(stem, fourths, fifths):        # ICD-10-AM 5-char codes
    return [f"{stem}.{f}{x}" for f in fourths for x in fifths]


GROUPS = {
    "Alcohol": ["E52", *f1x_range("F10"), "G31.2", "G62.1", "G72.1", "I42.6",
                "K29.2", "K29.20", "K29.21", "K70.0", "K70.1", "K70.2",
                "K70.3", "K70.4", "K70.9", "K85.2", "K86.0", "T51.0",
                "T51.1", "T51.2", "X45", "X65"],
    "Anaesthetics": ["T41.0", "T41.1", "T41.2", "T41.20", "T41.21",
                     "T41.22", "T41.29"],
    "Analeptics and opioid receptor antagonists": ["T50.7"],
    "Androgens and anabolic congeners": ["T38.7"],
    "Cannabinoids": [*f1x_range("F12"), "T40.7"],
    "Hallucinogens": [*f1x_range("F16"),
                      "F16.00", "F16.01", "F16.09", "F16.11", "F16.19",
                      "F16.20", "F16.21", "F16.29", "F16.30", "F16.31",
                      "F16.39", "F16.40", "F16.41", "F16.49", "F16.51",
                      "F16.59", "F16.60", "F16.61", "F16.69", "F16.70",
                      "F16.71", "F16.79", "F16.80", "F16.81", "F16.89",
                      "F16.90", "F16.91", "F16.99", "T40.8", "T40.9",
                      "X42", "X62"],
    "Inhalants": [*f1x_range("F18"), "X46", "X66"],
    "Multiple drug use": f1x_range("F19"),
    "Non-opioid analgesic and antirheumatic": [
        "F55.2", "T39.0", "T39.1", "T39.3", "T39.4", "T39.8", "T39.9",
        "X40", "X60"],
    "Opioid": [*f1x_range("F11"), "T40.0", "T40.1", "T40.2", "T40.3",
               "T40.4", "T40.6"],
    "Psychostimulants": [*f1x_range("F14"), *f1x_range("F15"),
                         *f1x_am5("F15", "0123456789", "0129"),
                         "T40.5", "T43.6", "T43.60", "T43.61", "T43.62",
                         "T43.69"],
    "Psychotropics (antidepressants, antipsychotics and neuroleptics)": [
        "F55.0", "T43.0", "T43.1", "T43.2", "T43.3", "T43.4", "T43.5",
        "T43.8", "T43.9"],
    "Sedative-hypnotics, antiepileptics and antiparkinson": [
        *f1x_range("F13"), *f1x_am5("F13", "0123456789", "019"),
        "T42.3", "T42.4", "T42.5", "T42.6", "T42.7", "X41", "X61"],
    "Steroids or hormones": ["F55.5"],
    "Other": ["K85.3", "X43", "X44", "X63", "X64"],
}


def describe(code):
    if code in FIXED:
        return FIXED[code]
    stem = code.split(".")[0]
    if stem in F1X_SUBSTANCE and "." in code:
        tail = code.split(".")[1]
        base = (f"Mental and behavioural disorders due to use of "
                f"{F1X_SUBSTANCE[stem]}, {F1X_QUALIFIER[tail[0]]}")
        if len(tail) == 2:
            base += f" (ICD-10-AM fifth-character subdivision {tail[1]})"
        return base
    if len(code) > 5 and code[:5] in FIXED:      # e.g. T41.21, K29.20, T43.61
        return (FIXED[code[:5]] +
                f" (ICD-10-AM fifth-character subdivision {code[5]})")
    return "Description pending — see ICD-10-AM tabular list"


rows = [dict(diagnosis_code=c, diagnosis_description=describe(c),
             diagnosis_group=g)
        for g, codes in GROUPS.items()
        for c in dict.fromkeys(codes)]        # de-dupe, keep order

ref = pd.DataFrame(rows)
assert ref.diagnosis_group.nunique() == 15, ref.diagnosis_group.nunique()
assert not ref.duplicated(["diagnosis_code", "diagnosis_group"]).any()
ref.to_csv("diagnosis_ref.csv", index=False)
print(f"Wrote diagnosis_ref.csv: {len(ref)} codes across "
      f"{ref.diagnosis_group.nunique()} groups")
print(ref.diagnosis_group.value_counts())
