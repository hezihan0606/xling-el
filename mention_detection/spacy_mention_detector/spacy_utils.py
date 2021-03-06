from typing import List, Tuple

import spacy
from spacy.tokens import Doc, Span, Token

from mention_detection.spacy_mention_detector import util


class WhitespaceTokenizer(object):
    def __init__(self, vocab):
        self.vocab = vocab

    def __call__(self, text):
        words = text.split(' ')
        # All tokens 'own' a subsequent space character in this tokenizer
        spaces = [True] * len(words)
        return Doc(self.vocab, words=words, spaces=spaces)


def getWhiteTokenizerSpacyNLP(disable_list: List[str] = ['textcat']):
    nlp = getSpacyNLP(disable_list)
    nlp.tokenizer = WhitespaceTokenizer(nlp.vocab)
    return nlp


def getSpacyNLP(model_name, disable_list: List[str] = ['textcat']):
    # nlp = spacy.load('en', disable=disable_list)
    nlp = spacy.load(model_name, disable=disable_list)
    return nlp


def getSpacyDocs(sents: List[str], nlp):
    """ Batch processing of sentences into Spacy docs."""
    return list(nlp.pipe(sents))


def getSpacyDoc(sent: str, nlp) -> Doc:
    """ Single sent to Spacy doc """
    return nlp(sent)


def getNER(spacydoc: Doc) -> List[Tuple[str, int, int, str]]:
    """Returns a list of (ner_text, ner_start, ner_end, ner_label). ner_end is exclusive. """
    assert spacydoc.is_tagged is True, "NER needs to run."

    ner_tags = []
    for ent in spacydoc.ents:
        ner_tags.append((ent.text, ent.start, ent.end, ent.label_))

    return ner_tags


def getPropnSpans(spacydoc: Doc) -> List[Tuple[str, int, int, str]]:
    pos_tags = getPOSTags(spacydoc)
    propn_span_srtend = util.getContiguousSpansOfElement(pos_tags, "PROPN")
    propn_spans = [(spacydoc[propnspan[0]:propnspan[1]].text, propnspan[0], propnspan[1], "PROPN") \
                   for propnspan in propn_span_srtend]

    return propn_spans


def getNER_and_PROPN(spacydoc: Doc) -> List[Tuple[str, int, int, str]]:
    """Returns a list of (ner_text, ner_start, ner_end, ner_label). ner_end is exclusive.
    This also includes PROPN spans that are not part of a NER
    """
    ner_tags = getNER(spacydoc)
    ner_spans = [(x, y) for (_, x, y, _) in ner_tags]

    pos_tags = getPOSTags(spacydoc)
    propn_spans = util.getContiguousSpansOfElement(pos_tags, "PROPN")

    propn_spans_tokeep = []
    for propnspan in propn_spans:
        add_propn = True
        for nerspan in ner_spans:
            if util.doSpansIntersect(propnspan, nerspan):
                add_propn = False
                break

        if add_propn:
            propn_spans_tokeep.append(propnspan)

    for propnspan in propn_spans_tokeep:
        ner_tags.append((spacydoc[propnspan[0]:propnspan[1]].text, propnspan[0], propnspan[1], "PROPN"))

    return ner_tags


def getPOSTags(spacydoc: Doc) -> List[str]:
    """ Returns a list of POS tags for the doc. """
    pos_tags = [token.pos_ for token in spacydoc]
    return pos_tags


def getTokens(spacydoc: Doc) -> List[str]:
    tokens = [token.text for token in spacydoc]
    return tokens


def getWhiteSpacedSent(spacydoc: Doc) -> str:
    """Return a whitespaced delimited spacydoc. """
    tokens = getTokens(spacydoc)
    return ' '.join(tokens)


def getAll_SentIdAndTokenOffset(spacydoc: Doc) -> List[Tuple[int, int]]:
    """Get (sentence idx, withinSentOffset) for all tokens."""
    numTokens = len(spacydoc)
    tokenIdxs = []
    sentence_end_pos = [sent.end for sent in spacydoc.sents]
    sent_idx = 0
    withinsent_tokenidx = 0

    for i in range(0, numTokens):
        if i == sentence_end_pos[sent_idx]:
            sent_idx += 1
            withinsent_tokenidx = 0

        tokenIdxs.append((sent_idx, withinsent_tokenidx))
        withinsent_tokenidx += 1
    return tokenIdxs


def getSpanHead(doc: Doc, span: Tuple[int, int]):
    """
    Returns token idx of the span root.
    :param doc: Spacy doc
    :param span_srt: Span start
    :param span_end: Span end (exclusive)
    :return: Token idx of the span head
    """
    assert doc.is_parsed, "Doc isn't dep parsed."
    doclength = len(doc)
    (span_srt, span_end) = span
    assert (span_srt >= 0) and (span_srt < doclength)
    assert (span_end > 0) and (span_end <= doclength)
    span: Span = doc[span_srt:span_end]
    spanroot: Token = span.root
    return spanroot.i


def getNERInToken(doc: Doc, token_idx: int):
    """
    If the given token is a part of NE, return the NE span, otherwise the input token's span
    :param doc: Spacy doc
    :param token_idx: int idx of the token
    :return: (srt-inclusive, end-exclusive)  of the NER (if matches) else (token_idx, token_idx + 1)
    """
    token: Token = doc[token_idx]
    ner_spans = [(ent.start, ent.end) for ent in doc.ents]

    if token.ent_iob_ == 'O':
        # Input token is not a NER
        return token_idx, token_idx + 1
    else:
        # Token is an NER, find which span
        # NER spans (srt, end) are in increasing order
        for (srt, end) in ner_spans:
            if srt <= token_idx < end:
                return (srt, end)
    print("I SHOULDN'T BE HERE")
    return token_idx, token_idx + 1


# def get_sentence(token):
#     for sent in token.doc.sents:
#         if sent.start <= token.i:
#             return sent
#
#
# # Add a computed property, which will be accessible as token._.sent
# Token.set_extension('sent', getter=get_sentence)


def get_tokenized_sentences(doc: Doc) -> List[List[Token]]:
    """
    Creates a list of list of Token objects, where each inner list is a sentence.
    :param doc:
    :return:
    """
    tokenized_sentences = []
    curr_sent_idx = 0
    curr_sent = []
    for tok_idx, (sent_idx, relative_tok_idx) in enumerate(getAll_SentIdAndTokenOffset(doc)):
        if sent_idx == curr_sent_idx:
            # print(doc[tok_idx].text, sent_idx)
            curr_sent.append(doc[tok_idx])
        else:
            curr_sent_idx = sent_idx
            tokenized_sentences.append(curr_sent)
            curr_sent = [doc[tok_idx]]
    # add the last sentence
    tokenized_sentences.append(curr_sent)

    # for sent in tokenized_sentences:
    #     print([tok.text for tok in sent])

    return tokenized_sentences


lang2spacy_model = {"en": 'en_core_web_lg',
                    "es": 'es_core_news_md',
                    "fr": 'fr_core_news_md',
                    "it": "it_core_news_sm",
                    "de": "de_core_news_sm"
                    }
