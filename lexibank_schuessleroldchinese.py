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
from sinopy import is_chinese


def parse_gloss(entry):
    
    gloss = re.findall("‘([^’]*?)’", entry)
    if gloss:
        return gloss[0]
    else:
        return "NA"

@attr.s
class CustomConcept(Concept):
    Number = attr.ib(default=None)
    Description = attr.ib(default=None)

#@attr.s
#class CustomLanguage(Language):
#    Latitude = attr.ib(default=None)
#    Longitude = attr.ib(default=None)
#    ChineseName = attr.ib(default=None)
#    SubGroup = attr.ib(default="Sinitic")
#    Family = attr.ib(default="Sino-Tibetan")
#    DialectGroup = attr.ib(default=None)


@attr.s
class CustomLexeme(Lexeme):
    Character = attr.ib(default=None)
    CharacterVariants = attr.ib(default=None)
    Pinyin = attr.ib(default=None)
    WordFamily = attr.ib(default=None)
    FormVariants = attr.ib(default=None)


class Dataset(BaseDataset):
    dir = Path(__file__).parent
    id = "schuessleroldchinese"
    lexeme_class = CustomLexeme
    concept_class = CustomConcept
    #language_class = CustomLanguage
    form_spec = FormSpec(
          missing_data=["", "--"],
          replacements=[(" ", "_"), ("*", ""), ("_!", "")],
          separators=";/,<~",
          brackets={"(": ")", "[": "]"},
          strip_inside_brackets=True,
          first_form_only=True
      )
    def cmd_download(self, **kw):
        self.raw_dir.write("sources.bib", getEvoBibAsBibtex("Schuessler2007", **kw))

    def cmd_makecldf(self, args):

        data = self.raw_dir.read_csv("SchuesslerTharsen.tsv", delimiter="\t",
                dicts=True)[1:]
        
        # add sources from raw/sources.bib
        args.writer.add_sources()
        
        # add languages (custom made here)
        for lang in ["Middle Chinese", 'Old Chinese', 'Late Han Chinese']:
            args.writer.add_language(
                    ID=lang.replace(" ", ""),
                    Name=lang
                    )

        # add concepts
        concepts = {}
        for row in progressbar(data):
            if row["QY_IPA"].strip():
                concept = parse_gloss(row["Notes"])
                idx = "{0}-{1}".format(row["ID"], slug(concept, lowercase=False))
                args.writer.add_concept(
                        ID=idx,
                        Name=concept,
                        Number=idx,
                        Description=row["Notes"])
                for lang, reading_ in [("OldChinese", "OCM_IPA"),
                        ("LateHanChinese", "LH_IPA"),
                        ("MiddleChinese", "QY_IPA")]:
                    reading = row[reading_].strip()
                    reading_variants = ""
                    if "or" in reading:
                        reading_variants = reading
                        reading = reading.split("or")[0].strip()
                    if is_chinese(reading):
                        args.log.info("{0} has wrong form {1} for {2}".format(
                            row["ID"],
                            row[reading_],
                            lang))
                    elif reading:
                        args.writer.add_forms_from_value(
                                Local_ID=row["pinyin_index"],
                                FormVariants=reading_variants,
                                Value=reading,
                                Parameter_ID=idx,
                                Language_ID=lang,
                                Character=row["graph"][0],
                                CharacterVariants=row["graph"] if len(row["graph"]) > 1 else "",
                                Cognacy=row["ID"],
                                Source="Schuessler2007",
                                WordFamily=row["wf_pinyin"].strip("{") or row["pinyin_index"].strip(),
                                Pinyin=row["pinyin_index"].strip("123456789")
                                )

          

