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


def parse_entry(entry):
    for sep in ["~", "⪤", "or", "=", "<"]:
        if sep in entry:
            entry = entry.split(sep)[0].strip()
            break
    if len(entry.split(" ")) == 2:
        pin, char = entry.split(" ")
        pin = pin.strip("₁₂₃₄₅₆₇₈₉₀")
        if len(char) == 1 and not is_chinese(char):
            return pin, char, '?'
        return pin, char, ''
    return entry, "", "!"
    

@attr.s
class CustomConcept(Concept):
    Number = attr.ib(default=None)
    Description = attr.ib(default=None)



@attr.s
class CustomLexeme(Lexeme):
    Chinese_Characters = attr.ib(default=None)
    Entry_In_Source = attr.ib(default=None)
    Pinyin = attr.ib(default=None)
    Misc = attr.ib(default=None)
    Sino_Tibetan_Cognates = attr.ib(default=None)



class Dataset(BaseDataset):
    dir = Path(__file__).parent
    id = "schuessleroldchinese"
    lexeme_class = CustomLexeme
    concept_class = CustomConcept
    #language_class = CustomLanguage
    form_spec = FormSpec(
          missing_data=["", "--"],
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
                    rest = ":".join(line.split(":")[1:])
                    for h in ["Middle Chinese", "Later Han", "Minimal Old Chinese"]:
                        if rest.startswith(h+":"):
                            rest = ":".join(rest.split(":")[1:])
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
                pinyin, char, problem = parse_entry(entry["HEAD"])
                if problem in ["!", "?"]:
                    problems.add((problem, entry["ENTRY"], entry["HEAD"]))
                else:
                    for lid, language in [
                            ("MiddleChinese", "MC"), 
                            ("LateHanChinese", "LH"), 
                            ("OldChinese", "OCM")]:
                        if language in entry:
                            args.writer.add_forms_from_value(
                                    Local_ID=entry["ENTRY"],
                                    Entry_In_Source=entry["HEAD"],
                                    Pinyin=pinyin,
                                    Chinese_Characters=char,
                                    Language_ID=lid,
                                    Value=entry[language].replace(" or ", "|"),
                                    Parameter_ID=cidx,
                                    Source="Schuessler2007",
                                    Cognacy=entry["ENTRY"],
                                    Misc=" ".join(entry["MISC"]),
                                    Sino_Tibetan_Cognates=" // ".join(entry["ST"])
                                    )

            else:
                count += 1
        args.log.info("skipped {0} entries without data".format(count))
        args.log.info("skipped {0} entries with problems".format(len(problems)))
        for p, e, h in list(problems)[:10]:
            print("{0} | {1:5} | {2}".format(p, e, h))


          

