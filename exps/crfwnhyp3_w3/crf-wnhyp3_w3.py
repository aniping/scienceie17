"""
Simple CRF exp with basic features (lemma & POS in a 5-token window),
using 5-fold CV for evaluation
"""

from os.path import join

from sklearn_crfsuite import CRF
from sklearn_crfsuite.metrics import flat_classification_report

from sklearn.model_selection import cross_val_predict, GroupKFold

from sie import ENTITIES, LOCAL_DIR, DATA_DIR
from sie.crf import collect_crf_data, pred_to_iob
from sie.feats import generate_feats
from sie.brat import iob_to_brat

from eval import calculateMeasures

# Function to add WordNet features
from nltk.corpus import wordnet as wn

def features2(sent, context_size=1, undefined='__'):
    """
    Example of a simple feature function which generates, for each token in
    the sentence, its lemma, POS and first hypernym of the first Wordnet synset of the first hypernym as well as that of the 
    preceding/following token (i.e. window size=3).

    Example:

    [
    {
      "-1:lemma": "__",
      "-1:pos": "__",
      "-1:wnhypernym3": "__",
      "0:lemma": "poor",
      "0:pos": "ADJ",
      "0:wnhypernym3": "Synset('abstraction.n.06')",
      "1:lemma": "oxidation",
      "1:pos": "NOUN",
      "1:wnhypernym3": "Synset('natural_process.n.01')"
    },
    {
      "-1:lemma": "poor",
      "-1:pos": "ADJ",
      "-1:wnhypernym3": "Synset('abstraction.n.06')",
      "0:lemma": "oxidation",
      "0:pos": "NOUN",
      "0:wnhypernym3": "Synset('natural_process.n.01')",
      "1:lemma": "behavior",
      "1:pos": "NOUN",
      "1:wnhypernym3": "Synset('event.n.01')"
    },
    {
      "-1:lemma": "oxidation",
      "-1:pos": "NOUN",
      "-1:wnhypernym3": "Synset('natural_process.n.01')",
      "0:lemma": "behavior",
      "0:pos": "NOUN",
      "0:wnhypernym3": "Synset('event.n.01')",
      "1:lemma": "be",
      "1:pos": "VERB",
      "1:wnhypernym3": "Synset('substance.n.01')"
    },

      ],
    """
    sent_feats = []

    for i, token in enumerate(sent):
            
        token_feats = {}

        for j in range(-context_size, context_size + 1):
            k = j + i

            if 0 <= k < len(sent):
                lemma = sent[k].lemma_
                pos = sent[k].pos_  
                if len(wn.synsets(lemma)) >= 1 and len(wn.synsets(lemma)[0].hypernyms()) >= 1 and len(wn.synsets(lemma)[0].hypernyms()[0].hypernyms()) >= 1 and len(wn.synsets(lemma)[0].hypernyms()[0].hypernyms()[0].hypernyms()) >= 1: 
                    wnhypernym3 = str(wn.synsets(lemma)[0].hypernyms()[0].hypernyms()[0].hypernyms()[0]) 
            else:
                lemma = pos = wnhypernym3 = undefined
                

            token_feats['{}:lemma'.format(j)] = lemma
            token_feats['{}:pos'.format(j)] = pos
            token_feats['{}:wnhypernym3'.format(j)] = wnhypernym3

        sent_feats.append(token_feats)

    return sent_feats



# Step 1: Generate features

spacy_dir = join(LOCAL_DIR, 'train', 'spacy')
feats_dir = join('_train', 'features2')

# If you want to save time by resusing feats from crf1-exp/py,
# comment out the line below:
generate_feats(spacy_dir, feats_dir, features2)

# Step 2: Collect data for running CRF classifier

true_iob_dir = join(LOCAL_DIR, 'train', 'iob')

data = collect_crf_data(true_iob_dir, feats_dir)

# Step 3: Create folds

# create folds from complete texts only (i.e. instances of the same text
# are never in different folds)
# TODO How to set seed for random generator?
group_k_fold = GroupKFold(n_splits=5)

# use same split for all three entities
splits = list(
    group_k_fold.split(data['feats'], data['Material'], data['filenames']))

# Step 4: Run CRF classifier
crf = CRF(c1=0.1, c2=0.1, all_possible_transitions=True)
pred = {}

for ent in ENTITIES:
    crf.fit(data['feats'], data[ent])
    pred[ent] = cross_val_predict(crf, data['feats'], data[ent], cv=splits)
    # Report scores directly on I and B tags,
    # disregard 'O' because it is by far the most frequent class
    print('\n' + ent + ':\n')
    print(flat_classification_report(data[ent], pred[ent], digits=3,
                                     labels=('B', 'I')))


# Step 5: Convert CRF prediction to IOB tags
pred_iob_dir = '_train/iob'

pred_to_iob(pred, data['filenames'], true_iob_dir, pred_iob_dir)

# Step 6: Convert predicted IOB tags to predicted Brat annotations
txt_dir = join(DATA_DIR, 'train')
brat_dir = '_train/brat'

iob_to_brat(pred_iob_dir, txt_dir, brat_dir)

# Step 7: Evaluate
calculateMeasures(txt_dir, brat_dir, 'rel')

