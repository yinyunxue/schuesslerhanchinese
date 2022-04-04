import attr
import lingpy
from pathlib import Path
from clldutils.misc import slug
from pylexibank import Concept, Language
from pylexibank.dataset import Dataset as BaseDataset
from pylexibank.forms import FormSpec
from pylexibank.util import progressbar, getEvoBibAsBibtex

from lingpy.sequence.sound_classes import syllabify
from pylexibank.models import Concept, Language, Lexeme
from pylexibank.dataset import Dataset as BaseDataset
from pylexibank.util import pb, getEvoBibAsBibtex

import re
from sinopy.util import is_chinese
from unicodedata import normalize


def parse_entry(entry, cognates):
    if  "⪤" in entry:
        entry = entry.split("⪤")[1].strip()
    for sep in ["~", "or", "=", "<"]:
        if sep in entry:
            entry = entry.split(sep)[0].strip()
            break
    if len(entry.split(" ")) == 2:
        cogs = []
        pin, char = entry.split(" ")
        pin = pin.strip("₁₂₃₄₅₆₇₈₉₀")
        if len(char) == 1 and not is_chinese(char):
            return pin, char, '?', []
        elif all(map(is_chinese, char)):
            for c in char:
                if c in cognates:
                    cogid = cognates[c]
                else:
                    cogid = max(cognates.values())+1
                    cognates[c] = cogid
                cogs += [str(cogid)]

        return pin, char, '', cogs
    return entry, "", "!", []


def a_b_distinction(entry, form_spec, lexemes):
    stypes = []
    entry = form_spec.split(None, lexemes.get(entry, entry))[0]
    for val in entry.strip("-").split("-"):
        if "\u0302" in normalize("NFD", val):
            stypes += ["A"]
        else:
            stypes += ["B"]
    return stypes
    

@attr.s
class CustomConcept(Concept):
    Number = attr.ib(default=None)
    Description = attr.ib(default=None)



@attr.s
class CustomLexeme(Lexeme):
    Chinese_Characters = attr.ib(default=None)
    Chinese_Character_Variants = attr.ib(default=None)
    Entry_In_Source = attr.ib(default=None)
    Pinyin = attr.ib(default=None)
    Misc = attr.ib(default=None)
    Sino_Tibetan_Cognates = attr.ib(default=None)
    Syllable_Types = attr.ib(default=None)



class Dataset(BaseDataset):
    dir = Path(__file__).parent
    id = "schuessleroldchinese"
    lexeme_class = CustomLexeme
    concept_class = CustomConcept
    form_spec = FormSpec(
            missing_data=["", "--", "?", "凱", "翹"],
            replacements=[(" ", "_"), ("*", ""), ("_!", "")],
            separators=";/,<~>|",
            brackets={"(": ")", "[": "]"},
            strip_inside_brackets=True,
            first_form_only=True
    )
    def cmd_download(self, **kw):
        self.raw_dir.write("sources.bib", getEvoBibAsBibtex("Schuessler2007", **kw))
        


    def cmd_makecldf(self, args):
        
        # add sources from raw/sources.bib
        args.writer.add_sources()
        
        # add languages (custom made here)
        for lang in ["Middle Chinese", 'Old Chinese', 'Late Han Chinese']:
            args.writer.add_language(
                    ID=lang.replace(" ", ""),
                    Name=lang
                    )

        entryr = {row["ENTRY"]: row["REPLACEMENT"] for row in self.etc_dir.read_csv("entries.tsv", delimiter="\t",
                    dicts=True)}

        with open(self.raw_dir / "schuesslerCooper.txt") as f:
            entries_ = f.read().split("\n\n")
        entries = {}
        for entry_ in entries_:
            entry = {"DESCRIPTION": [], "GLOSS": [], "MISC": [], "ST": []}
            for line in entry_.split("\n"):
                if line.startswith(" "):
                    entry["DESCRIPTION"] += [line.strip()]
                elif line.startswith(">"):
                    entry["MISC"] += [line[2:]]
                elif line.startswith(":"):
                    entry["ST"] += [line[2:]]
                elif ":" in line:
                    head = line[:line.index(":")]
                    rest = ":".join(line.split(":")[1:]).strip()
                    for h in ["Middle Chinese", "Later Han", "Minimal Old Chinese"]:
                        if rest.startswith(h+":"):
                            rest = ":".join(rest.split(":")[1:]).strip()
                    if head == "GLOSS":
                        entry["GLOSS"] += [rest]
                    else:
                        entry[head] = rest
            if "HEAD" in entry:
                if not entry["GLOSS"]:
                    entry["GLOSS"] = ["NA"]
                entries[entry["ENTRY"]] = entry
            else:
                args.log.info("no HEAD found in {0}".format(entry["ENTRY"]))
        args.log.info("found {0} entries".format(len(entries)))
        count, problems = 0, set()
        COG = {"0": 0}
        variant_count = 0
        for entry in entries.values():
            if "MC" in entry or "LH" in entry or "OCM" in entry:
                # get concept identifier
                gloss = entry["GLOSS"][0]
                cidx = "{0}-{1}".format(
                        entry["ENTRY"], 
                        slug(gloss, lowercase=False)
                        )
                args.writer.add_concept(
                        ID=cidx,
                        Name=gloss,
                        Description=" ".join(entry.get("GLOSS", [])),
                        )
                # get pinyin and the like
                pinyin, char, problem, cogids = parse_entry(entryr.get(entry["HEAD"], entry["HEAD"]), COG)
                if problem in ["!", "?"]:
                    problems.add((problem, entry["ENTRY"], entry["HEAD"]))
                else:
                    this_char = char
                    for lid, language in [
                            ("MiddleChinese", "MC"), 
                            ("LateHanChinese", "LH"), 
                            ("OldChinese", "OCM")]:
                        if language in entry:                            
                            variants = ""
                            current_cogids = [c for c in cogids]
                            tests = self.form_spec.split(
                                    None,
                                    self.lexemes.get(
                                        entry[language],
                                        entry[language])
                                    )
                            if tests: 
                                tests = tests[0].strip("-").split("-")
                                if len(tests) < len(current_cogids):
                                    current_cogids = current_cogids[:len(tests)]
                                    variants = " ".join([c for c in char[1:]])
                                    this_char = char[0]
                                    variant_count += 1
                                elif len(tests) > len(current_cogids):
                                    args.log.info("multiple syllables for {0} / {1} / {2}".format(
                                        language+" / " + char + " / "+" ".join(cogids)+" / "+entry["ENTRY"], 
                                        entryr.get(entry["HEAD"],
                                            entry["HEAD"]),
                                        self.lexemes.get(entry[language],
                                            entry[language])))
                                    current_cogids = current_cogids + ["0", "0", "0"]
                                    current_ogids = current_cogids[:len(tests)]

                            if language in ["OCM"]:
                                stypes = a_b_distinction(
                                        entry[language],
                                        self.form_spec, 
                                        self.lexemes)
                            else:
                                stypes = []

                            args.writer.add_forms_from_value(
                                    Local_ID=entry["ENTRY"],
                                    Entry_In_Source=entry["HEAD"],
                                    Pinyin=pinyin,
                                    Chinese_Characters=this_char,
                                    Chinese_Character_Variants=variants,
                                    Language_ID=lid,
                                    Value=entry[language].replace(" or ", "|"),
                                    Parameter_ID=cidx,
                                    Source="Schuessler2007",
                                    Cognacy=" ".join(current_cogids),
                                    Misc=" ".join(entry["MISC"]),
                                    Sino_Tibetan_Cognates=" // ".join(entry["ST"]),
                                    Syllable_Types=" ".join(stypes),
                                    )

            else:
                count += 1
        args.log.info("skipped {0} entries without data".format(count))
        args.log.info("skipped {0} entries with problems".format(len(problems)))
        args.log.info("found {0} characters with variants".format(variant_count))
        for p, e, h in list(problems)[:30]:
            print("{0} | {1:5} | {2}".format(p, e, h))


          

