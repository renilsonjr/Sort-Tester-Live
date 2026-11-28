"""Words a username may not contain (issue #515, owner decision 2026-11-28).

Racist, hateful and profane terms in English and Spanish. The words are
stored ROT13-encoded so this public repository does not print them in
plain text, and so a search of the code does not turn them up. This is
not a secret -- anyone can decode it -- it only keeps them off screens.
To add a word: ROT13 it (``codecs.encode(word, "rot13")``) and add it to
the right group.

ANYWHERE: matched inside the whole name, once look-alike characters are
mapped and ``_`` and digits are gone. Only words that never occur inside
an ordinary name belong here.
WHOLE_WORD: matched only as one whole part of the name (the parts are what
``_`` separates, with leading and trailing digits dropped), or as the whole
name. Short words that occur inside ordinary names belong here.
ALLOW: whole names that would otherwise be caught by an ANYWHERE word.
"""
import codecs


def _decode(block: str) -> frozenset[str]:
    return frozenset(codecs.decode(word, "rot13") for word in block.split())


ANYWHERE = _decode("""
    ornare ovgpu oybjwbo pnoeba pnoeban puvatn puvatnqn phyreb phag qvyqb
    snttbg sntbg shpx trabpvqr tvyvcbyynf urvyuvgyre uvwbqrchgn uvgyre xxx
    znycnevqn znycnevqb znznthrib znznuhrib znevpba znevpbanmb zvreqn
    zbgures artengn avttn avttre avtte crqbcuvyr craqrwn craqrwb chffl fuvg
    fvrturvy fyhg genaavr genaal jrgonpx juvgrcbjre juber
""")

WHOLE_WORD = _decode("""
    nefr nff nffubyr onfgneq puvax pbpx pbab pbba penc phyb phz qnza qvpx
    qlxr rfghcvqn rfghcvqb snt sntf shx tbbx ubr ubrf ubzb vqvbgn wvmm wbgb
    xvxr xvyy znzba znevpn zbatby anmv arten arteb cnwreb crqb creen cvwn
    cvatn cvff cvgb cbyyn cbea cevpx chgn chgnf chgb chgbf encr encvfg
    ergneq frk fcvp greebevfg grgn grgnf gvg gvgf gjng iretn jnax mbeen
""")

ALLOW = _decode("""
    crqeb crqebmn fphagubecr fuvvgnxr pbpxohea
""")
