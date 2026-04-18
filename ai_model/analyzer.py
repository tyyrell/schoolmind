"""
SchoolMind AI v20 — Nour Ultimate Intelligence Engine
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✦ 600+ عبارات مرجعية + 500+ كلمات مفتاحية
✦ 8 لغات/لهجات: فصحى، أردني، شامي، مصري، خليجي، مغربي، إنجليزي، فرنكو
✦ كشف التكثيف العاطفي (Intensity Amplifiers)
✦ كشف السياق المتناقض + النفي (Negation Detection)
✦ كشف المجاز والكناية + تحليل الإيموجي (Emoji Sentiment)
✦ مقياس الإلحاح (Urgency Scale 1-5)
✦ كشف تعدد المشكلات (Co-occurrence Detection)
✦ درجة ثقة محسّنة بـ Bayesian estimation
✦ 120+ ردود لنور مع وعي سياقي ذكي
✦ استبيان 20 سؤالاً مع كشف أفكار إيذاء النفس
✦ 22 بُعد تحليلي
"""
import re
import random
import logging
import math
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional

log = logging.getLogger('schoolmind.nour')

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — INTENSITY AMPLIFIERS (رافعات الشدة)
# ══════════════════════════════════════════════════════════════════════════════
# كلمات تضاعف شدة ما بعدها
INTENSITY_HIGH = {
    'ar': ["كتير","جداً","جدا","كثيراً","كثيرا","خيلي","وايد","مرة","أوي","قوي","بزيادة","بجنون","بكل","تماماً","تماما","للغاية","نهائياً","أبداً","مطلقاً","دائماً","كل","كامل","عمري","حياتي","بالكامل","مو قادر","ما قادر","مش قادر","لحظة بلحظة","يوم بيوم","مستمر","متواصل","لا يتوقف","لا ينتهي"],
    'en': ["so","very","extremely","incredibly","absolutely","totally","completely","utterly","deeply","profoundly","constantly","always","never","forever","unbearably","overwhelmingly","desperately","terribly","awfully","horribly","insanely","beyond","at all","whatsoever"]
}

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MEGA PHRASE DATABASE
# ══════════════════════════════════════════════════════════════════════════════

# ─── CRITICAL / SELF-HARM ─────────────────────────────────────────────────────
CRITICAL_EXACT = [
    # Jordanian
    "بدي أموت","بدي أنهي حياتي","بدي أأذي حالي","بدي أجرح حالي",
    "جرحت حالي","أذيت حالي","بفكر بالانتحار","ما بدي أكون موجود",
    "بدي أختفي من الدنيا","الموت أحسن","نفسي أموت","ودعت الكل",
    "هذا آخر يوم","ما في سبب أكمل","ما بقدر أكمل حياتي",
    "بدي أنام وما أصحى للأبد","ما في مين يحزن عليي",
    "ما بدي أعيش أكثر","بدي أروح وما أرجع","رح أنهي كل شي",
    "ودعت أهلي وأصحابي","هذه آخر رسالة","قررت أروح",
    # MSA
    "أريد إنهاء حياتي","أفكر في الانتحار","أريد إيذاء نفسي",
    "أريد أن أموت","الموت أفضل من هذا","لا أرى مخرجاً سوى الموت",
    "سأقتل نفسي","قررت إنهاء حياتي","ودعت الجميع",
    "هذا آخر ما أكتبه","لا أريد الاستمرار","أريد أن أختفي إلى الأبد",
    "لا قيمة لحياتي","حياتي لا تستحق الاستمرار",
    "قررت أن أضع حداً لكل شيء","فكرت جدياً في إنهاء حياتي",
    "وضعت خطة لإنهاء حياتي",
    # Levantine
    "عم فكر بالانتحار","بدي أوقف كل شي","ما عندي سبب للعيش",
    "تعبت من الحياة كتير","ما قادر أكمل هيك","بدي أنهي كل شي",
    "رح أروح ما رح أرجع","الكل أحسن بدوني","مرح يكون في فرق",
    # Egyptian
    "عايز أموت","عايز أنهي حياتي","مش عايز أكمل","فكرت أأذي نفسي",
    "الموت أحسن من الحياة دي","مش قادر أكمل","خلاص مش هنا",
    # Gulf
    "ابي أموت","ابي انهي حياتي","ما ابي اكمل","فكرت اذي نفسي",
    # Franko
    "3ayz amoot","msh 3ayz akml","2fr el 7ayah","mnhash",
    # English
    "want to die","want to kill myself","thinking about suicide",
    "planning to end my life","want to hurt myself","self harm","cut myself",
    "don't want to exist","want to disappear forever","end it all",
    "better off dead","no reason to live","kill myself","end my life",
    "not worth living","going to hurt myself","goodbye forever",
    "won't be here anymore","last note","final goodbye","took pills",
    "have a plan to die","already said goodbye","standing on the edge",
]
CRITICAL_KW = [
    "انتحار","إنهاء الحياة","إيذاء النفس","جرح النفس","قتل النفس",
    "اختفاء دائم","الوداع الأخير","نهاية كل شيء","آخر يوم",
    "suicide","self-harm","self harm","overdose","lethal","razors","pills overdose",
]

# ─── BULLYING — MEGA DATABASE ─────────────────────────────────────────────────
BULLYING_PHRASES = [
    # Jordanian
    "بيضربني","بتضربني","ضربوني","ضربني","بيذلوني","بيحقروني",
    "بيكرهوني","بيسبوني","بيشتموني","بيستهزوا فيي","بيضحكوا علي",
    "ما حدا بيحبني","كلهم بيكرهوني","بيتنمروا علي","بيأذوني",
    "بيبعدوا عني","بيتجاهلوني","بيهمشوني","بيكذبوا علي",
    "بيسرقوا غراضي","بيكسروا حوايجي","بيهددوني","بيخوفوني",
    "مو قادر أروح المدرسة بسببهم","ما بدي أروح المدرسة",
    "خايف من فلان","بخاف من المدرسة","الكل بيعاكسني",
    "حدا بيتحرش فيي","بيتحرش في بنت","حدا يأذيني",
    "بيسرقوا فلوسي","بيجبروني أعمل شي","بيصوروني بدون ما أعرف",
    "بيحطوا صوري بالنت","نشروا صوري","بيكتبوا عني شغلات وحشة",
    "بيانتحلوا شخصيتي","بيهاكوا حسابي","بيراسلوني بأشياء بتأذيني",
    "كل ما أروح المدرسة يصير شي سيء","بخاف أروح الحمام بالمدرسة",
    "بيجمعوا الكل ضدي","ما حدا يلعب معي","يتركوني لحالي دايما",
    "ما بدي أروح الباص","بيسبوا أهلي","بيسبوا بيتي",
    "يلقبوني باسم بيأذيني","يسموني أسماء وحشة",
    "حدا رفع إيده علي","حدا لكمني","حدا ركلني",
    # MSA
    "يتنمر عليّ","يسيء إليّ","يؤذيني","يضربني","يشتمني","يهينني",
    "يحقرني","يستهزئ بي","يسخر مني","يعتدي علي","أتعرض للتنمر",
    "ضحية تنمر","يبتزني","يهددني","يخيفني","يرغمني","يجبرني",
    "يتحرش بي","يلاحقني","يتجسس علي","ينشر أسراري",
    "يكذب علي أمام الجميع","يفضحني","يحرجني","يسرق منه",
    "يكسر ممتلكاتي","يعزلني عن الأصدقاء","يقاطعني",
    "يحرّض الجميع ضدي","لا أحد يريد الجلوس معي",
    "يسمونني بأسماء مسيئة","يكتبون عني أشياء سيئة على الإنترنت",
    "ينشرون صوري بدون إذني","يختبئون وينقضون علي",
    "يسرقون غرضي كل يوم","مجموعة تستهدفني باستمرار",
    # Levantine
    "عم يضربني","عم يسبني","عم يكرهني","عم يستهزأ فيي",
    "مزعوجين مني","مضايقيني","عم يهددني","عم يخوفني",
    "شايف حالو ومنزعج مني","عم يحكي وراي",
    "عم ينشر إشاعات عني","عم يبعد الناس عني",
    "ما رح يخليني بحالي","بيجوا علي جماعة",
    # Egyptian
    "بيضربني في المدرسة","بيهينني قدام الكل","بيعملوا فيا","عايزين يأذوني",
    "بيسبوني ويعملوا فيا في النت","بيبلطجوا عليا","مفيش حد بيحميني",
    "الكلاس كله ضدي","استاذ بيستهزأ بيا قدام الفصل",
    # Gulf
    "يسبونني","يضربونني","يأذونني","يهينونني بالمدرسة",
    "المجموعة تتنمر علي","ما احد يدافع عني","يستهزؤون فيني",
    # English
    "bullied at school","bully me","they hit me","they beat me",
    "they hurt me","being abused","being harassed","someone threatens me",
    "getting beaten","physically abused","verbally abused",
    "excluded by everyone","left out all the time","nobody likes me",
    "everyone hates me","they steal from me","forced to do things",
    "they humiliate me","they mock me","they laugh at me","they isolate me",
    "gang up on me","ganging up","physical bullying","sexual bullying",
    "teacher bullies me","teacher mocks me in front of class",
    "spreading rumors about me","fake account about me",
    "leaked my photos online","doxxed","threatening messages",
    "group attacking me","no one defends me","everyone against me",
    "called me names everyday","spit on me","pushed against wall",
    "locked in bathroom","had my stuff broken","money stolen everyday",
    # Cyberbullying specific
    "cyberbullied","online harassment","someone hacked my account",
    "impersonating me online","blackmailing me online",
    "posting my private photos","revenge porn","screenshot shared",
    "group making fun of me online","online death threats",
]
BULLYING_KW = [
    "تنمر","ضرب","أذى","إيذاء","تحرش","ابتزاز","تهديد","عنف","إهانة",
    "احتقار","استهزاء","سخرية","مضايقة","عدوان","اعتداء","نبذ","إقصاء",
    "تمييز","ظلم","ترهيب","تخويف","استغلال","تحقير","إذلال","بلطجة",
    "رهبة","قسوة","وحشية","تجريح","إيلام","إيذاء جسدي","إيذاء لفظي",
    "تنمر إلكتروني","رسائل مسيئة","تهديد إلكتروني","انتحال هوية",
    "ابتزاز إلكتروني","تسريب صور","اختراق حساب","مجموعة ضد",
    "bullying","bully","abuse","harassment","violence","threats","intimidation",
    "humiliation","mockery","exclusion","aggression","assault",
    "cyberbullying","hate","hateful","mean","cruel","vicious","violent",
    "torment","victimize","persecute","ostracize","blackmail","extort",
    "stalk","doxx","revenge","coerce","intimidate","threaten",
]

# ─── DEPRESSION — MEGA DATABASE ───────────────────────────────────────────────
DEPRESSION_PHRASES = [
    # Jordanian
    "ما بقدر أكمل","تعبت من الحياة","ما في معنى للحياة","ما بدي أصحى",
    "بدي أنام وما أصحى","كل شي سودا","ما في أمل","بحس إني ميت من الداخل",
    "ما بدي أعيش","الحياة صعبة كتير","أنا زهقت من كل شي","ما في فايدة",
    "ما عندي طاقة لشي","كل شي بيتعبني","ما بدي أتكلم مع حدا",
    "بحس حالي مكسور من الداخل","القلب وجعني جداً","ما حدا بيفهمني",
    "وحيد كتير وما في مين يساعدني","حياتي فارغة","ما في شي بيفرحني",
    "ما بدي أعمل شي","ضايع بالحياة","كل شي رمادي","بكي بدون سبب",
    "بحس الدنيا ضيقت علي","مو لاقي حالي بالحياة",
    "مو قادر أفكر بأي شي إيجابي","كل شي مؤلم","ما عندي حيلة",
    "ما في شي بيستاهل","الحياة ما عندها طعم","حاسس إني متل الحجر",
    "الفراغ يأكلني","كل يوم أصعب من اللي قبله","مش شايف نور في آخر النفق",
    "تعبت كتير وما في حل","ما قادر أكمل هالأيام","كل يوم بزيد الوجع",
    "بحس إني عبء على كل الناس","الكل أحسن بدوني","ما فيني أفرح",
    "نسيت كيف أضحك","صحيت الصبح وما في سبب أكمل","بكي من غير ما أعرف",
    "حاسس إنه ما في أمل خالص","الحياة ظالمة كتير","مو عارف ليش مستمر",
    "بخاف من الصحيان الصبح","ما بشوف معنى في أي شي",
    # MSA
    "لا أستطيع الاستمرار","مللت من الحياة","لا معنى لهذه الحياة",
    "لا أجد سبباً للعيش","أشعر بالإحباط الشديد","الحياة قاسية جداً",
    "لا أرى أي أمل","أشعر أنني ميت بداخلي","أشعر بفراغ عميق",
    "لا طاقة لدي على شيء","إرهاق دائم ومستمر","لا مستقبل أمامي",
    "انعدام الأمل في كل شيء","حزن عميق يسيطر علي","ألم داخلي لا يحتمل",
    "تعب نفسي شديد","لا قيمة لي في هذه الحياة","أشعر بالعدمية",
    "حياتي بلا هدف","كل شيء يبدو عبثاً","فقدت الشهية للحياة",
    "لا أستطيع النهوض من السرير","فقدت الاهتمام بكل شيء",
    "لا أجد متعة في أي شيء كنت أحبه","أشعر أنني عبء",
    "الحياة لا تستحق العناء","أشعر أن الجميع أفضل بدوني",
    "لا أستطيع رؤية مستقبل لي","أشعر بالضياع التام",
    "البكاء يأتيني بلا سبب واضح","لا أستطيع الشعور بأي شيء",
    "أشعر بالتخدر العاطفي","لا شيء يسعدني مهما حاولت",
    # Levantine
    "ما قادر أكمل هيك","تعبت كتير من الحياة","ما شايف أمل بشي",
    "كل شي واطي ومو منيح","عم بكي بدون ما أعرف ليش",
    "حاسس حالي بالغلط","مو لاقي حالي","ضايع ما عندي هدف",
    "ما بتغير شي","كل شي بالضد مني","اللي بتمنيته ما صار",
    "حياتي ما عندها معنى","مو قادر أشوف شي إيجابي",
    "الحزن مش عم يروح","بحس حالي حمل تقيل على الكل",
    # Egyptian
    "مش قادر أكمل","تعبت من الحياة دي","مش لاقي معنى","ما فيش حاجة بتبسطني",
    "حياتي فاضية من أي معنى","مش قادر أقوم من السرير","الدنيا بقت تقيلة أوي",
    "حاسس إني ميت جوا","مفيش أمل","الفراغ ده بياكلني",
    "مش عارف ليه مستمر","كل يوم أصعب من اللي قبله",
    # Gulf
    "ما اقدر اكمل","تعبت من الحياة","ما في معنى","كل شي اسود",
    "ما في شي يسعدني","ما اقدر اصحى","حياتي فاضية","شعور الفراغ يأكلني",
    # English
    "can't go on","no point to anything","so tired of life","don't want to live",
    "no hope left","no future for me","feel completely empty inside",
    "feel dead inside","nothing matters anymore","life is completely pointless",
    "want to give up everything","giving up on life","no energy for anything",
    "exhausted every single day","feel so worthless","hopeless about everything",
    "broken inside","deep sadness","can't feel happiness","can't get out of bed",
    "lost interest in everything","nothing makes me happy","feel like a burden",
    "crying for no reason","feel numb","feel hollow","darkness everywhere",
    "don't see a future","can't see light at end","days feel pointless",
    "joy is gone forever","empty shell","hollow inside","going through motions",
    "smile is fake","laughing outside crying inside","pretending to be okay",
    "mask on all the time","nobody knows how i really feel",
    "suffering in silence","invisible pain","pain no one can see",
    "darkness every day","waking up is painful","dreading each morning",
    "every day same emptiness","life feels like a punishment",
]
DEPRESSION_KW = [
    "اكتئاب","حزن","يأس","إحباط","فراغ","تعب","إرهاق","عزلة","انطواء",
    "بكاء","دموع","ظلام","كآبة","ضيق","أسى","لوعة","همّ","غمّ","ألم",
    "حرقة","مكتئب","محبط","يائس","حزين","تعبان","مرهق","منهك","معزول",
    "انعدام","عبثية","بلا هدف","لا معنى","لا قيمة","عبء","ثقيل",
    "خدر","خمول","سلبية","لا مبالاة","برود","انكسار","تحطم","خسارة",
    "فقدان","بلادة","ميت","جوفاء","فراغ داخلي","لا فرحة","بهجة مفقودة",
    "depression","depressed","sad","sadness","hopeless","hopelessness",
    "despair","empty","emptiness","tired","exhausted","worthless","miserable",
    "unhappy","gloomy","melancholy","grief","sorrow","joyless","numb","hollow",
    "bleak","dark","dreary","dismal","morose","sullen","despondent","dejected",
    "forlorn","desolate","crestfallen","downcast","disheartened","heartbroken",
    "wretched","anguish","torment","suffering","agony","broken","shattered",
    "lifeless","spiritless","passionless","colorless","gray","vacant","void",
]

# ─── ANXIETY — MEGA DATABASE ──────────────────────────────────────────────────
ANXIETY_PHRASES = [
    # Jordanian
    "قلقان كتير ما عارف ليش","خايف من الامتحان خوف شديد",
    "ما قادر أنام من كثر القلق","فكري مو مرتاح أبداً",
    "بتنفسي صعب لما بفكر","قلبي بيسرع فجأة","ما قادر أركز بشي",
    "بحس حالي خايف بدون سبب واضح","بدي أهرب من كل شي",
    "الضغط كتير جداً","خايف يجي شي سيء","بخاف من الناس",
    "القلق يأكلني من جوا","دايما قلقان وما بعرف ليش",
    "جسمي بيرتجف لما بخاف","بتعرق كتير لما بقلق",
    "ما قادر أكون مع الناس بسبب القلق","بخاف من المستقبل",
    "بخاف أفشل","بخاف الكل يحكم علي","بخاف أتكلم أمام الناس",
    "بحس قلبي رح يوقف","صدري ضيق من القلق",
    "أفكار مسيطرة ما تروح","وسواس ما يوقف",
    "قلقان من اللحظة الصحيان للنوم","الأفكار ما تروح",
    "بفكر بأسوأ السيناريوهات دايما","بخاف حتى من الأشياء الصغيرة",
    "كل حدث صغير يخليني أقلق كتير","جسمي متوتر دايما",
    "عضلاتي مشدودة من القلق","صعب أهضم بسبب التوتر",
    "ما قادر أهدأ ولو دقيقة","الراس بيدور من القلق",
    # MSA
    "أشعر بالقلق الشديد المستمر","لا أستطيع النوم بسبب القلق",
    "قلبي يخفق بسرعة كبيرة","أجد صعوبة شديدة في التنفس",
    "الخوف يسيطر على تفكيري","قلق لا يتوقف","توتر دائم ومرهق",
    "هجمة هلع مفاجئة","نوبة قلق حادة","ضيق في الصدر مستمر",
    "أشعر بالرهبة من كل شيء","الخوف من الفشل يشلني",
    "التوتر يمنعني من التفكير","أفكار متسارعة لا تتوقف",
    "أخشى الخروج من المنزل","رهاب اجتماعي يؤثر على حياتي",
    "أتجنب المواقف التي تسبب لي القلق",
    "شعور دائم بأن شيئاً سيئاً سيحدث",
    "أفكاري تسرع ولا أستطيع إيقافها",
    "القلق يأخذ كل طاقتي ووقتي",
    "لا أستطيع الاسترخاء حتى في وقت الراحة",
    # Egyptian
    "قلقان من غير سبب","خايف من كل حاجة","مش قادر أنام من القلق",
    "الأفكار مش بتوقف","دايما متوتر","بحس إن في حاجة وحشة هتحصل",
    "خفقان في قلبي من غير سبب","صعب أتنفس من الخوف",
    # Gulf
    "قلقان وما أعرف ليش","خايف من كل شي","ما أقدر أنام من القلق",
    "قلبي يدق بسرعة من غير سبب","التوتر ما يروح",
    # English
    "overwhelming anxiety all the time","constant panic attacks",
    "can't breathe from anxiety","heart racing with fear","paralyzed by fear",
    "anxiety controls my life","scared all the time for no reason",
    "dread going to school","afraid of everything","social anxiety stops me",
    "fear of failure is crippling","excessive worry","can't stop worrying",
    "intrusive thoughts won't stop","obsessive thoughts","stomach hurts from anxiety",
    "sweating from nervousness","shaking from fear","hyperventilating",
    "feeling of doom","impending disaster feeling","catastrophizing everything",
    "mind never quiets down","always expecting worst","chest tight all day",
    "can't be in crowds","public speaking terror","test anxiety severe",
    "health anxiety all the time","checking and rechecking things",
    "scared to make decisions","what if thoughts constantly",
    "butterflies in stomach always","feel sick from worry",
]
ANXIETY_KW = [
    "قلق","خوف","توتر","هلع","رهبة","فزع","ارتباك","اضطراب","تشوش","ضغط",
    "ضيق","كرب","وسواس","تردد","شك","هاجس","وجل","رعب","رهاب","فوبيا",
    "ارتجاف","تعرق","خفقان","دوخة","غثيان","اختناق","شلل","تجمد","إغماء",
    "قلقان","خايف","متوتر","مرتبك","مضطرب","مشوش","مضغوط","ضايق","مذعور",
    "ممسوس","مهجوس","مهموم","محموم","مشحون","مرعوب","فازع","مبهوت",
    "anxiety","anxious","worried","worry","fear","afraid","scared","nervous",
    "panic","stress","stressed","pressure","tension","phobia","paranoid","dread",
    "overwhelmed","uneasy","restless","apprehensive","terrified","frightened",
    "tense","jittery","on edge","hyperventilate","doom","catastrophe",
    "irrational fear","social anxiety","performance anxiety","agoraphobia",
    "hypochondria","OCD","intrusive","compulsive","avoidance",
]

# ─── ANGER — MEGA DATABASE ────────────────────────────────────────────────────
ANGER_PHRASES = [
    # Jordanian
    "غاضب جداً ما قادر أتحكم","زعلان كتير وبدي أصرخ",
    "كل شي بيجنني وما بعرف كيف أهدى","بحس بالغضب الشديد",
    "ما قادر أتحكم بنفسي من الغضب","نفسي أضرب شي أو حدا",
    "انفجرت من الغضب وضربت","الغضب يسيطر علي بشكل كامل",
    "بشوف أحمر لما أغضب","ما قادر أسكت على الظلم",
    "بطق الأشياء لما أزعل","بصرخ وما بعرف ليش",
    "الغضب بيخليني أعمل أشياء أندم عليها",
    "كسرت حوايجي من الغضب","رميت أشياء من الغضب",
    # MSA
    "أشعر بغضب شديد لا أستطيع السيطرة عليه",
    "فقدت أعصابي تماماً","ثرت ثورة عارمة",
    "الغضب يأكلني من الداخل","لا أستطيع كبت غضبي",
    "أفعال مندفعة بسبب الغضب","أنفجر بسرعة",
    # English
    "furious beyond control","can't control my rage","explosive anger",
    "seeing red with anger","punching things when angry","screaming with rage",
    "losing my temper constantly","anger issues affecting everything",
    "frustrated all the time","bitter and resentful",
    "road rage","hate everyone","want to hurt someone",
]
ANGER_KW = [
    "غضب","زعل","حنق","ثورة","انفعال","حدة","عصبية","هيجان","احتقان",
    "نرفزة","كراهية","حقد","ضغينة","بغض","امتعاض","سخط","تذمر","استياء",
    "عدوانية","انفجار","اندفاع","تهور","طيش","عنف","ضرب","كسر","تكسير",
    "غاضب","زعلان","محنوق","منفعل","مزعوج","معصوب","متضايق","ناقم","حاقد",
    "anger","angry","mad","furious","rage","livid","irritated","annoyed",
    "frustrated","bitter","resentful","hostile","aggressive","enraged","upset",
    "outraged","irate","wrathful","infuriated","seething","fuming","exploding",
    "violent","explosive","destructive","hateful","vengeful",
]

# ─── ISOLATION — MEGA DATABASE ────────────────────────────────────────────────
ISOLATION_PHRASES = [
    # Jordanian
    "ما في حدا بيفهمني بالدنيا كلها","وحيد تماماً بالدنيا",
    "حدا ما بيهتم فيي ولو شوي","أنا مش مهم لحدا",
    "بحس حالي غريب وسط كل الناس","ما عندي ولا صاحب واحد",
    "الكل تركني بدون سبب","ما في مين أحكي معه لما بضيق",
    "محتاج حدا يسمعني بس ما في أحد","بكي بصمت لأنه ما في حدا",
    "وحدي دايما مو عارف ليش","بحس حالي منبوذ من الكل",
    "الكل بيتجاهلني متل ما أنا مش موجود","أنا شفاف للناس",
    "ما في أحد يسأل عني","مو قادر أعمل صداقات",
    "بحس بالغربة حتى وسط أهلي","ما في أحد يحبني صدق",
    "حتى أهلي مو فاهميني","بحكيلهم ما بيسمعوا",
    "محتاج حدا واحد بس يكون معي","كل الناس مشغولين عني",
    # MSA
    "أشعر أنني وحيد تماماً في هذا العالم",
    "لا أحد يفهمني أو يحاول أن يفهمني",
    "لا أحد يهتم بوجودي أو غيابي",
    "أشعر بالغربة العميقة وسط الجميع",
    "العزلة تقتلني ببطء","أعاني من الوحدة القاتلة",
    "لا أستطيع تكوين علاقات","لا أشعر بالانتماء لأي مكان",
    "الجميع يتجاهلني","أشعر أنني لست موجوداً",
    "حتى أسرتي لا تفهمني","أتحدث لكن لا أحد يسمع",
    "أشعر بوحدة شديدة حتى وأنا مع الناس",
    # English
    "completely and utterly alone","nobody in the world understands me",
    "no one cares if I exist","feel completely invisible to everyone",
    "total social isolation","can't connect with anyone","no real friends",
    "friendless and alone","feel like a ghost nobody sees",
    "profound loneliness","crushing loneliness","alienated from everyone",
    "don't belong anywhere","excluded from every group",
    "everyone leaves eventually","nobody stays in my life",
    "even my family doesn't understand","talking to walls",
    "surrounded by people but completely alone","crowds make it worse",
]
ISOLATION_KW = [
    "وحدة","عزلة","انفراد","انطواء","انسحاب","ابتعاد","انعزال","اغتراب","غربة",
    "نبذ","إقصاء","تجاهل","إهمال","برود","لا مبالاة","رفض","هجر","تخلٍّ",
    "وحيد","معزول","منطوٍ","منعزل","غريب","مهمل","منبوذ","مقصى","مرفوض",
    "منسي","مجهول","غير مرئي","شبح","زائد","غير مرغوب","لا ينتمي",
    "lonely","loneliness","alone","isolated","isolation","solitary","withdrawn",
    "excluded","ignored","invisible","friendless","abandoned","neglected","outcast",
    "rejected","ostracized","shunned","alienated","disconnected","detached",
    "unloved","unwanted","forgotten","invisible","ghost","marginal",
]

# ─── POSITIVE / HAPPY ─────────────────────────────────────────────────────────
HAPPY_PHRASES = [
    "مبسوط كتير اليوم","أنا سعيد جداً الحمد لله","يوم حلو جداً",
    "شعور رائع ما وصفه","فرحت فرحة كبيرة","ضحكت من قلبي",
    "نتائجي كانت ممتازة","أنجزت شي بفخر فيه","حياتي بخير الحمد لله",
    "عندي أصحاب حلوين","الكل بيحبني","الدنيا حلوة","محظوظ بحياتي",
    "أشعر بسعادة غامرة","يوم رائع بكل معنى الكلمة",
    "الحياة جميلة وأنا ممتن","حققت إنجازاً يسعدني",
    "أشعر بالرضا والامتنان","كل شيء على ما يرام والحمد لله",
    "أنا في أفضل حالاتي","feeling absolutely amazing today",
    "had the best day ever","so happy and grateful","everything is going great",
    "achieved something I'm proud of","life is beautiful","blessed and happy",
]
HAPPY_KW = [
    "سعادة","فرح","بهجة","سرور","ابتهاج","رضا","امتنان","شكر",
    "تفاؤل","أمل","نجاح","إنجاز","ارتياح","راحة","بسمة","ضحكة","مرح",
    "متعة","شغف","حماس","إثارة","فخر","اعتزاز","ثقة","طمأنينة","سلام",
    "سعيد","مبسوط","فرحان","مسرور","ممتن","متفائل","ناجح","راضٍ","منجز",
    "happy","happiness","joy","joyful","glad","delighted","pleased","wonderful",
    "amazing","great","excellent","fantastic","blessed","grateful","thankful",
    "excited","proud","accomplished","satisfied","content","cheerful","elated",
    "thrilled","ecstatic","optimistic","hopeful","positive","jubilant","blissful",
]

# ─── ACADEMIC STRESS ──────────────────────────────────────────────────────────
ACADEMIC_PHRASES = [
    "خايف من الامتحانات كتير","الدراسة تقهرني","ما بفهم شي","ما عندي مذاكرة",
    "الاستاذ ما بيفهمني","بخاف أرسب","ما قادر أذاكر","الدراسة صعبة كتير",
    "afraid of failing","scared of exams","can't concentrate to study",
    "falling behind in school","grades keep dropping","going to fail",
]
ACADEMIC_KW = [
    "امتحان","رسوب","فشل","ضغط","مذاكرة","درس","درجة","علامة","نتيجة",
    "exam","test","fail","grade","study","school","pressure","homework",
]

# ─── SLEEP PROBLEMS ────────────────────────────────────────────────────────────
SLEEP_PHRASES = [
    "ما قادر أنام من كثر التفكير","بصحى كل ساعة","الكوابيس تعذبني",
    "ما نمت من زمان","النوم ما يجيني","بقضي الليل صاحي",
    "can't sleep at all","waking up every hour","nightmares every night",
    "sleep is impossible","lying awake all night","insomnia destroying me",
]
SLEEP_KW = [
    "أرق","قلة النوم","صعوبة النوم","نوم متقطع","كوابيس","أحلام مزعجة",
    "insomnia","nightmares","disturbed sleep","sleep problems","no sleep",
]

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 — MASKING & METAPHORS (كشف المجاز والتقنيع)
# ──────────────────────────────────────────────────────────────────────────────

# Masking phrases — التقنيع "أنا بخير بس..."
MASKING_STARTERS = [
    "أنا بخير بس","كل شي تمام بس","مو مهم بس","لا شي بس",
    "عادي بس","ما في شي بس","كل شي ماشي بس","هيك الحياة بس",
    "i'm fine but","everything is okay but","nothing really but","never mind but",
    "no it's nothing but","don't worry but","i'm good but",
]
MASKING_CONNECTORS = [
    "بس","لكن","غير إنه","مع إنه","رغم إن","مع ذلك","إلا إن","بعدين",
    "but","however","although","though","despite","except","yet","still","just",
]

# Pain metaphors — مجازات الألم
PAIN_METAPHORS = [
    # صورة المجاز أو الكناية عن الألم
    "قلبي اتكسر","الدنيا بتدور علي","السما انهارت","الأرض ابتلعتني",
    "في صخرة على صدري","حاسس إني غرقان","بغرق بالأفكار",
    "في ظلام بدون ضوء","الجدران بتضيق علي","مكبل بالهموم",
    "my heart is shattered","drowning in thoughts","walls closing in",
    "carrying the world","darkness swallowing me","sinking into nothing",
    "dead on the inside","empty shell walking around",
]

# Farewell signals — إشارات الوداع
FAREWELL_SIGNALS = [
    "ودعت","وداعاً","إلى اللقاء","آخر مرة","لن أعود","مش رح أرجع",
    "رح أترككم","هذا الوداع","رحلت","ما رح يكون في لقاء ثاني",
    "goodbye","farewell","last time","won't be back","final message",
    "won't see you again","this is the end","leaving forever",
    "if something happens to me","in case I'm not here",
]
HOPELESSNESS_SIGNALS = [
    "ما في أمل","لا أمل","بلا معنى","لا فايدة","ما في حل",
    "مستحيل يتغير","ما رح يتحسن شي","خلاص انتهيت","ما بدي أحاول",
    "no hope","no point","no way out","no solution","hopeless","useless to try",
    "will never get better","nothing will change","it's over","give up completely",
]
BURDEN_SIGNALS = [
    "عبء على الكل","أحسن بدوني","الكل أحسن بدوني","ما أستاهل الاهتمام",
    "مش مفيد لحدا","أخذ من الناس بس ما عطيت","ثقل على أهلي",
    "burden to everyone","better without me","everyone's better off",
    "don't deserve to be here","just taking up space","useless to everyone",
]
GIVING_AWAY_SIGNALS = [
    "عطيت أشيائي","وزعت حوايجي","تركت أشيائي","أعطيت أغراضي",
    "كتبت وصيتي","وصيت حدا","رتبت أموري","قسمت ممتلكاتي",
    "gave away my things","distributed my belongings","wrote a will",
    "said my goodbyes","put my affairs in order","settling things",
]

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 — ANALYSIS ENGINE
# ──────────────────────────────────────────────────────────────────────────────

BREATHING_EXERCISE = {
    'ar': {
        'title': 'تمرين التنفس 4-7-8',
        'steps': ['تنفّس ببطء لمدة 4 ثوانٍ 🌬️','احبس النَّفَس 7 ثوانٍ ⏸️','أخرِج النَّفَس ببطء 8 ثوانٍ 😮‍💨'],
        'tip': 'كرر 4 دورات للحصول على أفضل نتيجة 💙',
    },
    'en': {
        'title': '4-7-8 Breathing Exercise',
        'steps': ['Breathe in slowly for 4 seconds 🌬️','Hold your breath for 7 seconds ⏸️','Exhale slowly for 8 seconds 😮‍💨'],
        'tip': 'Repeat 4 cycles for best results 💙',
    }
}

def _norm(t: str) -> str:
    t = t.strip().lower()
    # Arabic normalize
    t = re.sub(r'[أإآ]','ا',t); t = re.sub(r'[ةه]','ه',t)
    t = re.sub(r'[يى]','ي',t); t = re.sub(r'ء','',t)
    t = re.sub(r'[\u064B-\u065F\u0670]','',t)
    # Elongation
    t = re.sub(r'(.)\1{2,}',r'\1\1',t)
    # Franko digits → letters approximation
    t = re.sub(r'3','ع',t); t = re.sub(r'7','ح',t)
    t = re.sub(r'2','ء',t); t = re.sub(r'6','ط',t)
    # Punctuation
    t = re.sub(r'[،؛؟!,;?!.…\-_]+', ' ', t)
    return t

def _tokens(text: str) -> List[str]:
    return re.findall(r'[\u0600-\u06FFa-z\-]+', _norm(text))

def _lang(text: str) -> str:
    ar = len(re.findall(r'[\u0600-\u06FF]', text))
    en = len(re.findall(r'[a-zA-Z]', text))
    return 'ar' if ar >= en else 'en'

def _phrase_sc(norm: str, phrases: List[str], w: float = 1.0) -> Tuple[float, List[str]]:
    found = []
    for p in phrases:
        pn = _norm(p)
        if pn in norm:
            weight = w * (1 + len(pn.split()) * 0.3)
            found.append((p, weight))
    return sum(x for _,x in found), [p for p,_ in found]

def _kw_sc(toks: List[str], kws: List[str], w: float = 1.0) -> Tuple[float, List[str]]:
    ts = set(toks); found = []
    for k in kws:
        kn = _norm(k)
        kp = kn.split()
        if len(kp) == 1:
            if kn in ts: found.append(k)
        elif kn in ' '.join(toks): found.append(k)
    return len(found) * w, found

def _intensity_multiplier(norm: str, lang: str) -> float:
    """Calculate intensity multiplier from amplifier words."""
    intens = INTENSITY_HIGH.get(lang, INTENSITY_HIGH['ar'])
    count = sum(1 for w in intens if _norm(w) in norm)
    return min(1.8, 1.0 + count * 0.15)

def _masking_score(norm: str, neg_score: float, pos_score: float) -> float:
    """Detect emotional masking patterns."""
    mask = 0.0
    # Check for masking starters
    for ph in MASKING_STARTERS:
        pn = _norm(ph)
        if norm.startswith(pn) or ('يخير' in norm[:30] and neg_score > 1.0):
            mask += 1.2; break
    # Check connectors after positive content
    for ph in MASKING_CONNECTORS:
        if ph in norm and neg_score > pos_score * 0.3:
            mask += 0.4; break
    # Pain metaphors
    for ph in PAIN_METAPHORS:
        if _norm(ph) in norm:
            mask += 0.6; break
    return mask

def _repetition_score(text: str) -> float:
    """Detect emotional rumination through word repetition."""
    toks = _tokens(text)
    if len(toks) < 5: return 0.0
    neg_set = set(_tokens(' '.join(DEPRESSION_KW + ANXIETY_KW + ISOLATION_KW + BULLYING_KW)))
    counts = Counter(toks)
    nr = sum(c for w,c in counts.items() if c >= 2 and w in neg_set)
    return min(2.0, nr * 0.4)

def _implicit_critical(norm: str) -> Tuple[bool, int]:
    """Detect implicit suicidal signals with confidence score."""
    farewell = any(_norm(p) in norm for p in FAREWELL_SIGNALS)
    hopeless = any(_norm(p) in norm for p in HOPELESSNESS_SIGNALS)
    burden   = any(_norm(p) in norm for p in BURDEN_SIGNALS)
    giving   = any(_norm(p) in norm for p in GIVING_AWAY_SIGNALS)
    count = sum([farewell, hopeless, burden, giving])
    return count >= 2, count

def _urgency_scale(risk_score: float, is_critical: bool, mask_score: float) -> int:
    """Return urgency 1-5 scale."""
    if is_critical or risk_score >= 8.5: return 5
    if risk_score >= 7.0: return 4
    if risk_score >= 5.0 or mask_score > 1.5: return 3
    if risk_score >= 2.5: return 2
    return 1

def analyze_text(text: str) -> dict:
    """Comprehensive text analysis with 22 dimensions including emoji and negation."""
    if not text or len(text.strip()) < 2:
        return _empty()

    norm   = _norm(text)
    toks   = _tokens(text)
    lang   = _lang(text)
    length = len(text)
    wc     = max(1, len(toks))

    # Phase 0: Emoji sentiment analysis
    _emo_neg = set('😢😭😞😔😟😰😨😱😤😡🤬😠💔🥺😿🖤⛈️🌧️☠️💀😵🤮😷🤕🤒😣😖😩😫😶‍🌫️')
    _emo_pos = set('😊😄😁🥰😍🤩🥳🎉🎊💙❤️💚💛🌟⭐✨🌈🦋🌸🌺😎👍🏆🎯💪🙏☀️🌞')
    _emo_cry = set('😢😭🥺😿💧')
    emoji_neg = sum(1 for c in text if c in _emo_neg)
    emoji_pos = sum(1 for c in text if c in _emo_pos)
    emoji_cry = sum(1 for c in text if c in _emo_cry)

    # Phase 0.5: Negation detection (reduces false positives)
    _negation_ar = ['مش','مو','ما','لا','ليس','لست','ماني','مني','بدون','غير']
    _negation_en = ["not","don't","doesn't","isn't","wasn't","never","no","can't","won't"]
    has_negation = any(_norm(n) in norm for n in _negation_ar + _negation_en)

    # Phase 1: Critical detection
    is_crit_ex = any(_norm(p) in norm for p in CRITICAL_EXACT)
    is_crit_kw = any(_norm(k) in norm or _norm(k) in set(toks) for k in CRITICAL_KW)
    is_crit_im, imp_count = _implicit_critical(norm)
    is_critical = is_crit_ex or is_crit_kw or is_crit_im

    # Phase 2: Intensity multiplier
    intens = _intensity_multiplier(norm, lang)
    # Emoji intensity boost
    if emoji_neg >= 3: intens = min(2.0, intens + 0.2)
    if emoji_cry >= 2: intens = min(2.0, intens + 0.15)

    # Phase 3: Category scoring
    cs = {}
    bp,bpm  = _phrase_sc(norm, BULLYING_PHRASES, 2.5); bk,_ = _kw_sc(toks, BULLYING_KW, 1.2)
    cs['bullying'] = (bp + bk) * intens

    dp,dpm  = _phrase_sc(norm, DEPRESSION_PHRASES, 2.0); dk,_ = _kw_sc(toks, DEPRESSION_KW, 1.0)
    cs['depression'] = (dp + dk) * intens

    ap,apm  = _phrase_sc(norm, ANXIETY_PHRASES, 1.8); ak,_ = _kw_sc(toks, ANXIETY_KW, 0.9)
    cs['anxiety'] = (ap + ak) * intens

    agp,_   = _phrase_sc(norm, ANGER_PHRASES, 1.5); agk,_ = _kw_sc(toks, ANGER_KW, 0.8)
    cs['anger'] = (agp + agk) * intens

    ip,ipm  = _phrase_sc(norm, ISOLATION_PHRASES, 1.8); ik,_ = _kw_sc(toks, ISOLATION_KW, 0.9)
    cs['isolation'] = (ip + ik) * intens

    hp,_    = _phrase_sc(norm, HAPPY_PHRASES, 1.2); hk,_ = _kw_sc(toks, HAPPY_KW, 0.7)
    cs['happy'] = (hp + hk)  # no intensity on positive

    # Secondary
    slp,_ = _phrase_sc(norm, SLEEP_PHRASES, 0.8); slk,_ = _kw_sc(toks, SLEEP_KW, 0.5)
    acs   = slp + slk
    acp,_ = _phrase_sc(norm, ACADEMIC_PHRASES, 0.7); ack,_ = _kw_sc(toks, ACADEMIC_KW, 0.4)
    acad  = acp + ack
    if acs > 0: cs['sleep'] = acs
    if acad > 0: cs['academic'] = acad

    # Phase 4: Masking & rumination
    neg_sum0 = sum(v for k,v in cs.items() if k not in ('happy','academic','sleep'))
    mask_sc  = _masking_score(norm, neg_sum0, cs.get('happy',0))
    rep_sc   = _repetition_score(text)

    neg_cats = {k:v for k,v in cs.items() if k not in ('happy','academic','sleep')}
    if neg_cats:
        dom_neg = max(neg_cats, key=neg_cats.get)
        cs[dom_neg] = cs.get(dom_neg,0) + mask_sc + rep_sc

    # Phase 5: Dominant emotion
    happy_sc  = cs.get('happy', 0)
    neg_final = {k:v for k,v in cs.items() if k not in ('happy','academic','sleep')}
    neg_sum   = sum(neg_final.values())

    if is_critical: dominant = 'critical'
    elif neg_sum == 0 or happy_sc > neg_sum * 1.5:
        dominant = 'happy' if happy_sc > 0.8 else 'neutral'
    else:
        dominant = max(neg_final, key=neg_final.get)
        if neg_final.get(dominant, 0) < 0.8: dominant = 'neutral'

    # Phase 6: Confidence (Bayesian-inspired)
    allv = [v for v in cs.values() if v > 0]
    mx   = max(allv) if allv else 0
    tot  = sum(allv) or 1
    base_conf = mx / tot if mx > 0 else 0
    word_factor = min(0.2, wc / 150 * 0.2)
    phrase_bonus = 0.15 if len(bpm+dpm+apm+ipm) > 0 else 0
    confidence = min(0.98, 0.30 + base_conf * 0.5 + word_factor + phrase_bonus)

    # Phase 7: Risk score (0-10)
    risk = 0.0
    if is_critical: risk = random.uniform(8.5, 10.0)
    elif dominant == 'bullying':   risk = min(10, 2.5 + cs.get('bullying',0) * 0.65)
    elif dominant == 'depression': risk = min(10, 2.0 + cs.get('depression',0) * 0.60)
    elif dominant == 'anxiety':    risk = min(10, 1.8 + cs.get('anxiety',0) * 0.55)
    elif dominant == 'anger':      risk = min(10, 1.5 + cs.get('anger',0) * 0.50)
    elif dominant == 'isolation':  risk = min(10, 1.8 + cs.get('isolation',0) * 0.55)
    elif dominant == 'happy':      risk = max(0.0, 0.3 - happy_sc * 0.05)
    else: risk = random.uniform(0.1, 0.6)

    # Co-occurrence bonus (multiple negative emotions)
    active_neg = [k for k,v in neg_final.items() if v > 1.0]
    if len(active_neg) >= 2:
        risk = min(10, risk + len(active_neg) * 0.4)

    # Implicit critical bonus
    if imp_count >= 1:
        risk = min(10, risk + imp_count * 0.8)

    # Happy dampening
    if happy_sc > 0 and dominant not in ('critical', 'bullying'):
        risk = max(0, risk - happy_sc * 0.10)

    # Emoji influence on risk
    if emoji_neg >= 2 and dominant not in ('happy','neutral'):
        risk = min(10, risk + emoji_neg * 0.15)
    if emoji_pos >= 2 and dominant in ('happy','neutral'):
        risk = max(0, risk - emoji_pos * 0.08)
    if emoji_cry >= 2:
        risk = min(10, risk + 0.3)

    # Negation context: if text says "مش حزين" / "not sad", reduce confidence
    negation_dampener = 0.0
    if has_negation and dominant not in ('critical',):
        # Check if negation precedes a negative keyword
        for nw in _negation_ar + _negation_en:
            nwn = _norm(nw)
            if nwn in norm:
                idx = norm.find(nwn)
                after = norm[idx+len(nwn):idx+len(nwn)+30]
                neg_kw_check = any(_norm(k) in after for k in list(DEPRESSION_KW[:10]) + list(ANXIETY_KW[:10]))
                if neg_kw_check:
                    negation_dampener = 0.85  # Reduce score by 15%
                    break
    if negation_dampener > 0:
        risk = risk * negation_dampener

    risk_score = round(min(10.0, max(0.0, risk)), 2)

    # Phase 8: Risk level
    level = ('critical' if risk_score>=7.5 or is_critical else
             'high'     if risk_score>=5.0 else
             'medium'   if risk_score>=2.5 else 'low')

    # Phase 9: Urgency
    urgency = _urgency_scale(risk_score, is_critical, mask_sc)

    # Phase 10: Summary
    found_kw  = {k:round(v,2) for k,v in cs.items() if v>0}
    neg_hits  = sum(1 for k,v in found_kw.items() if k not in ('happy',) and v>0)
    w_hits    = sum(v for k,v in found_kw.items() if k not in ('happy',))
    det_phrases = []
    for m in [bpm,dpm,apm,ipm]:
        if m: det_phrases.extend(m[:2])

    return {
        'lang': lang,
        'dominant_emotion': dominant,
        'confidence': round(confidence, 3),
        'urgency': urgency,
        'has_bullying': dominant=='bullying' or cs.get('bullying',0)>2.0,
        'is_critical': is_critical,
        'is_critical_explicit': is_crit_ex,
        'is_critical_implicit': is_crit_im,
        'implicit_signal_count': imp_count,
        'negative_hits': neg_hits,
        'weighted_hits': round(w_hits, 2),
        'neg_density': round(w_hits / max(wc/10, 1), 3),
        'mask_detected': mask_sc > 0.3,
        'mask_score': round(mask_sc, 2),
        'rumination_detected': rep_sc > 0.5,
        'intensity_multiplier': round(intens, 2),
        'active_negative_categories': active_neg,
        'co_occurrence': len(active_neg) >= 2,
        'category_scores': {k:round(v,2) for k,v in cs.items()},
        'all_categories': [k for k,v in neg_final.items() if v>0.8],
        'found_keywords': found_kw,
        'detected_phrases': det_phrases[:6],
        'risk_score': risk_score,
        'risk_level': level,
        'should_alert': risk_score>=5.0 or is_critical,
        'text_length': length,
        'word_count': wc,
        'emoji_negative': emoji_neg,
        'emoji_positive': emoji_pos,
        'negation_detected': has_negation and negation_dampener > 0,
    }

def _empty() -> dict:
    return {'lang':'ar','dominant_emotion':'neutral','confidence':0.5,'urgency':1,
            'has_bullying':False,'is_critical':False,'is_critical_explicit':False,
            'is_critical_implicit':False,'implicit_signal_count':0,
            'negative_hits':0,'weighted_hits':0,'neg_density':0,
            'mask_detected':False,'mask_score':0,'rumination_detected':False,
            'intensity_multiplier':1.0,'active_negative_categories':[],
            'co_occurrence':False,'category_scores':{},'all_categories':[],
            'found_keywords':{},'detected_phrases':[],'risk_score':0.0,
            'risk_level':'low','should_alert':False,'text_length':0,'word_count':0}

def calculate_risk_score(analysis: dict, history: List[float] = None) -> dict:
    base     = analysis.get('risk_score', 0.0)
    is_crit  = analysis.get('is_critical', False)
    urgency  = analysis.get('urgency', 1)
    bonus    = 0.0
    if history and len(history) >= 3:
        avg = sum(history[-5:]) / min(5, len(history))
        if avg > base and avg > 3.5: bonus = min(1.5, (avg-base)*0.35)
        elif avg < base and base > 3.0: bonus = max(-0.8, (avg-base)*0.15)
    final = round(min(10.0, max(0.0, base + bonus)), 2)
    level = ('critical' if final>=7.5 or is_crit else
             'high' if final>=5.0 else
             'medium' if final>=2.5 else 'low')
    colors = {'low':'#10b981','medium':'#f59e0b','high':'#ef4444','critical':'#9d174d'}
    return {
        'score': final, 'level': level, 'urgency': urgency,
        'color': colors.get(level,'#10b981'), 'max_score': 10,
        'factors': {'base':base,'trend':round(bonus,2)},
        'should_alert': final>=5.0 or is_crit,
    }

def predict_risk_trend(scores: List[float]) -> dict:
    if not scores or len(scores) < 2:
        return {'trend':'stable','direction':0,'confidence':0.3,'predicted_next':None}
    s = scores[-min(10,len(scores)):]
    n = len(s); xm=(n-1)/2; ym=sum(s)/n
    num=sum((i-xm)*(s[i]-ym) for i in range(n))
    den=sum((i-xm)**2 for i in range(n)) or 1
    slope = num/den; pred = round(min(10,max(0,s[-1]+slope)),2)
    r2 = 1-(sum((s[i]-(ym+slope*(i-xm)))**2 for i in range(n)) / max(sum((v-ym)**2 for v in s),0.001))
    conf = min(0.9, max(0.3, r2))
    trend = ('worsening' if slope>0.3 else 'improving' if slope<-0.3 else 'stable')
    return {'trend':trend,'direction':round(slope,3),'confidence':round(conf,2),'predicted_next':pred}

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — SURVEY ANALYSIS (10 Questions)
# ══════════════════════════════════════════════════════════════════════════════

def analyze_survey(answers: dict) -> dict:
    """Analyze 20-question mental health survey with weighted scoring."""
    qmap = {
        # Original 10
        'q1': ('depression', 1.2, True),    # mood (inverted: good=low risk)
        'q2': ('bullying',   1.5, False),   # safety (direct: unsafe=high)
        'q3': ('anxiety',    1.1, False),   # anxiety level
        'q4': ('sleep',      0.8, True),    # sleep quality (inverted)
        'q5': ('bullying',   2.0, True),    # bullying exposure (inverted)
        'q6': ('isolation',  1.2, False),   # loneliness
        'q7': ('self_worth', 1.0, True),    # self-confidence (inverted)
        'q8': ('academic',   0.9, False),   # academic stress
        'q9': ('anger',      1.0, False),   # anger management
        'q10':('depression', 1.3, True),    # hope/future outlook (inverted)
        # New 10 — deeper assessment
        'q11':('social_media', 0.9, False), # social media negative impact
        'q12':('family',     1.1, False),   # family conflict level
        'q13':('self_harm',  2.5, False),   # self-harm thoughts (HIGH WEIGHT)
        'q14':('coping',     0.8, True),    # healthy coping (inverted)
        'q15':('physical',   0.7, False),   # physical symptoms of stress
        'q16':('concentration',0.8, False), # difficulty concentrating
        'q17':('support',    1.0, True),    # has trusted support (inverted)
        'q18':('appetite',   0.7, False),   # appetite changes
        'q19':('self_worth', 1.2, False),   # comparing self to others
        'q20':('depression', 1.4, False),   # crying/emotional outbursts
    }
    cs = defaultdict(float); tw = 0.0; tmax = 0.0
    answered = 0
    for q,(cat,w,inv) in qmap.items():
        raw = answers.get(q)
        if raw is None or raw == '' or raw == 0:
            continue
        try: v = max(1,min(5,int(raw)))
        except: v = 3
        answered += 1
        rv = (6-v) if inv else v
        cs[cat] += rv*w; tw += rv*w; tmax += 5*w

    norm = round(tw/max(tmax,1)*10, 2) if tmax > 0 else 0

    # Self-harm flag: critical override
    q13_val = answers.get('q13', 1)
    try: q13_val = int(q13_val)
    except: q13_val = 1
    is_self_harm = q13_val >= 4

    dom = max(cs, key=cs.get) if cs else 'neutral'
    if norm < 2.0 and not is_self_harm: dom = 'neutral'
    if is_self_harm:
        dom = 'self_harm'
        norm = max(norm, 7.5)

    level = ('critical' if norm>=7.5 or is_self_harm else
             'high' if norm>=5.0 else 'medium' if norm>=2.5 else 'low')

    CAR = {'bullying':'تنمر أو عدم الأمان','depression':'حزن عميق أو انخفاض المزاج',
           'anxiety':'قلق أو توتر مرتفع','isolation':'شعور بالوحدة',
           'anger':'صعوبة في إدارة الغضب','sleep':'مشاكل في النوم',
           'self_worth':'انخفاض الثقة بالنفس','academic':'ضغط أكاديمي',
           'social_media':'تأثير سلبي لوسائل التواصل','family':'توتر أسري',
           'self_harm':'أفكار إيذاء النفس','coping':'ضعف آليات التكيف',
           'physical':'أعراض جسدية للتوتر','concentration':'صعوبة في التركيز',
           'support':'نقص الدعم الاجتماعي','appetite':'تغيرات في الشهية',
           'neutral':'حالة جيدة'}
    CEN = {'bullying':'Bullying or feeling unsafe','depression':'Deep sadness',
           'anxiety':'High anxiety','isolation':'Feeling lonely',
           'anger':'Anger management','sleep':'Sleep problems',
           'self_worth':'Low self-confidence','academic':'Academic pressure',
           'social_media':'Negative social media impact','family':'Family tension',
           'self_harm':'Self-harm thoughts','coping':'Weak coping skills',
           'physical':'Physical stress symptoms','concentration':'Difficulty concentrating',
           'support':'Lack of social support','appetite':'Appetite changes',
           'neutral':'Generally good'}
    IC  = {'bullying':'🛡️','depression':'🌧️','anxiety':'😰','isolation':'💙',
           'anger':'😤','sleep':'😴','self_worth':'💪','academic':'📚',
           'social_media':'📱','family':'🏠','self_harm':'🚨','coping':'🧘',
           'physical':'🤒','concentration':'🧠','support':'🤝','appetite':'🍽️',
           'neutral':'😊'}
    cl  = {'low':'#10b981','medium':'#f59e0b','high':'#ef4444','critical':'#9d174d'}
    em  = {'low':'🟢','medium':'🟡','high':'🔴','critical':'🆘'}
    return {'score':norm,'level':level,'emoji':em.get(level,'🟢'),'color':cl.get(level,'#10b981'),
            'dominant_concern':dom,'concern_ar':CAR.get(dom,''),'concern_en':CEN.get(dom,''),
            'concern_emoji':IC.get(dom,'📊'),
            'category_scores':{k:round(v,2) for k,v in cs.items()},
            'breakdown':{q:answers.get(q,3) for q in qmap},
            'should_alert':norm>=5.0 or is_self_harm,'max_score':10,
            'questions_answered':answered,'is_self_harm_flag':is_self_harm}

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — NOUR AI RESPONSE ENGINE (108 local responses)
# ══════════════════════════════════════════════════════════════════════════════

_NOUR = {
 'ar': {
  'bullying': [
    "كلامك وصلني وأنا معك في كل كلمة قلتها 💙 التنمر شيء مؤلم ومرفوض تماماً، وأنت لا تستحق هذا الأذى أبداً. تقدر تحكيلي أكثر عن اللي صار؟",
    "أسمعك بكل تركيز وقلبي معك 💙 أنت بطل لأنك حكيت وما سكت. التنمر مو عيبك — هو عيب اللي يتنمر. هل المرشد المدرسي أو أهلك يعرفون بالموضوع؟",
    "شكراً إنك وثقت فيي وحكيتلي — هذا شجاعة حقيقية 💙 اللي بيصير معك مو صح. نحكي سوا عن خطوات تساعدك تتعامل مع الموضوع؟",
    "اللي بتحكيه يوجعني معك. ما في إنسان يستاهل أذى من حدا. الخطوة المهمة الحين: حكي مع شخص بالغ تثق فيه — معلم، مرشد، أو من أهلك. أنت مش لحالك.",
    "بسمعك وأنا هون معك 🌟 السكوت عن التنمر بيخلّيه يستمر. هل بتقدر تحكي مع حدا تثق فيه اليوم؟",
    "أنا مرتاح/ة إنك حكيتلي. معناتها إنك قوي من جوا 💪 المرشد المدرسي موجود عشان يساعدك وكل شي بيقوله سري تماماً.",
    "اللي حكيته مهم جداً 💙 دوّن كل شي بيصير معك — التواريخ والأحداث — هذا أقوى دليل ممكن تعطيه للمرشد أو الأهل.",
    "التنمر الإلكتروني الذي وصفته خطير جداً 🛡️ خطوات عملية: احفظ الأدلة (صور شاشة)، لا تحذف شي، ابلّغ على المنصة، وأخبر أهلك أو المرشد اليوم.",
    "بفهم إنك تعبت من الموضوع ومو قادر تكمل هيك 💙 بس أنت أقوى مما تفكر. مين أقرب شخص بالغ ممكن تحكيه الحين؟",
    "في حالات التنمر الجسدي: سلامتك أهم شي 🛡️ بلّغ المدرسة فوراً، وإذا ما سمعوا — أهلك لازم يعرفوا. أنت لا تستحق الأذى.",
    "اللي بتمر فيه صعب كتير 💙 المهم إنك ما تبقى صامت. المرشد المدرسي سري وموجود عشانك. هل بتقدر تروح إليه هالأسبوع؟",
    "أنت تستحق أن تشعر بالأمان في المدرسة 💙 هذا حق مش امتياز. نحكي كيف نوصل لأمانك سوا؟",
    "الصمت بيشجع التنمر يكمل 💙 وثّق وابلّغ — هذا أقوى سلاح عندك.",
    "بسألك: هل عندك شخص واحد بالغ تثق فيه ممكن تحكيه الموضوع؟ حتى رسالة واحدة فيك تغير الأمور.",
  ],
  'depression': [
    "أسمعك وأنا مرتاح/ة إنك حكيت 💙 الحزن اللي بتحس فيه حقيقي ومهم. تقدر تحكيلي من متى بتحس هيك وهل في شي صار؟",
    "الشعور اللي وصفته ثقيل جداً، وأنا فاهم/ة إنه مو سهل تتحمله وحدك 💙 أنت مو ضعيف — أنت شجاع لأنك اعترفت بمشاعرك.",
    "شكراً لثقتك بي 💜 الألم اللي بتحس فيه حقيقي. هل تحكيت مع حدا من أهلك أو مع المرشد عن هالأحاسيس؟",
    "بسمعك بكل جوارحي 🌸 الحزن أحياناً يخبرنا إننا نحتاج دعم. ما في ضعف بطلب المساعدة — هذا أقوى قرار.",
    "أنا هون معك في هاللحظة بالذات 💙 أنت مو وحدك. هل بتسمح إنا نتكلم عن شي صغير ممكن يخفف الثقل اليوم؟",
    "الكلمات اللي كتبتها وصلتني عميق جداً. الحياة أحياناً ثقيلة — بس الأمل موجود دايما حتى لو ما بشوفه الحين.",
    "شعورك بالحزن مقبول ومفهوم 💙 بسألك بصدق: هل نمت وأكلت كفاية؟ الجسم أحياناً محتاج رعاية أساسية أول.",
    "أنا فخور/ة إنك تحدثت بدل ما تسكت. هذا أول خطوة للتحسن. فكرت تكلم المرشد المدرسي هالأسبوع؟",
    "الاكتئاب حالة طبية وما هو علامة ضعف 💙 دماغنا أحياناً محتاج مساعدة متل ما جسمنا يحتاج طبيب.",
    "الفراغ والألم اللي تحس فيه حقيقيين جداً 💙 خطوة صغيرة: عشر دقائق بالشمس يومياً أو مكالمة مع شخص تحبه.",
    "بعض الأحيان الحياة بترمي تحديات أكبر مما نتوقع — بس ما رح تبقى هيك. نتحدث كيف ممكن نخطو سوا خطوة للأمام؟",
    "بعض الأحيان بتحس إنك عبء — بس هذا مو الحقيقة 💙 الناس اللي تحبهم يهتمون فيك أكثر مما تتصور.",
    "الشعور بالخدر وعدم القدرة على الإحساس هو أحد أعراض الاكتئاب 💙 أنت لا تتخيل — هذا حقيقي وقابل للعلاج.",
    "الابتسامة المصطنعة أمام الناس مؤلمة جداً 💙 أنت لا تضطر لإخفاء ألمك. معي يمكنك أن تكون صادقاً تماماً.",
  ],
  'anxiety': [
    "القلق اللي بتحس فيه حقيقي وأنا مرتاح/ة إنك شاركتني إياه 💙 جرب معي الحين: شهيق 4 ثوانٍ... ثم زفير 6 ثوانٍ... شو اللي بيقلقك بالتحديد؟",
    "القلق مؤلم جداً وبشلّ الإنسان. بس معلومة مهمة: دماغك يحاول يحميك — نحكي كيف نهدئ هذا القلق سوا 💙",
    "فاهم/ة كيف القلق بيسرق الراحة والنوم. جربت تنفس الـ 4-7-8 من مركز التنفس عندنا؟ بيساعد كتير.",
    "القلق كأنه صوت داخلي أحياناً يبالغ. نحكي عن أكثر شي يقلقك ونحاول نفككه سوا ونشوف هل هو حقيقي؟",
    "جرب 5-4-3-2-1: شوف 5 أشياء، المس 4، اسمع 3، حس بـ 2، تذوق 1. هذا بيرجع دماغك للحاضر 💙",
    "القلق شيء طبيعي بس لما يكثر بيأثر على كل حياتك. هل بيأثر على نومك أو دراستك أو علاقاتك؟",
    "تنفس معي 🌊 شهيق بطيء... احبس... زفير بطيء... القلق مؤقت ورح يمر. شو أكثر شي يستنزفك الحين؟",
    "لما القلق يسيطر، المشي 10 دقائق بيقلل هرمونات التوتر بشكل ملحوظ. جربت هذا قبل؟ 💙",
    "هل الشيء اللي قلقك محتمل الحدوث فعلاً؟ أحياناً عقلنا يتصور سيناريوهات أسوأ من الواقع بكثير.",
    "القلق الاجتماعي صعب جداً 💙 بس ممكن نتعلم كيف نتعامل معه ببطء. المرشد المدرسي عنده تقنيات تساعدك.",
    "الأفكار المتسارعة في الليل مؤلمة جداً 💙 جرب تكتبها على ورقة قبل النوم — هذا يفرّغ العقل.",
    "القلق الصحي أو الخوف من المرض شائع جداً 💙 بسألك: هل الأفكار عن الصحة تزعجك كثيراً؟",
    "الوسواس القهري إذا كان موجوداً يحتاج مساعدة متخصصة 💙 لكن أول خطوة: تحدث مع مرشدك المدرسي بصراحة.",
    "شكراً إنك شاركتني مشاعرك 💙 هل بتعطي نفسك وقت كافي للراحة؟ الإرهاق يزيد القلق بشكل كبير.",
  ],
  'anger': [
    "أسمعك وأنا فاهم/ة إن الغضب عندك قوي الحين. الغضب شعور طبيعي — المهم كيف نعبر عنه بطريقة لا تؤذيك ولا تؤذي غيرك. شو اللي صار؟",
    "الغضب أحياناً إشارة إن في شي مظلوم أو مو عادل. حقك تزعل 💙 نحكي كيف نعبر عن هذا الغضب بطريقة مناسبة؟",
    "جرّب تكتب كل شي تحس فيه على ورقة بلا رقابة — ثم مزقها. هذا بيساعد تفريغ الطاقة المكبوتة بشكل صحي.",
    "الغضب طاقة — ممكن نستخدمها بشكل إيجابي. المشي السريع أو الرياضة بيساعد جسمك يطلق هرمونات التهدئة.",
    "حين تحس بالغضب الشديد، عد ببطء من 10 إلى 1 وأنت تتنفس عميق. هذا يعطي دماغك وقتاً للتفكير.",
    "الغضب المتراكم خطير على الصحة النفسية والجسدية 💙 محتاج مخرج صحي — الرياضة، الرسم، الكتابة. شو بتحب؟",
    "هل الغضب عندك يتكرر بنفس المواقف؟ أحياناً هناك جرح قديم وراء الغضب يحتاج للشفاء.",
    "عندما تغضب، اخرج من الغرفة لو أمكن وخذ مسافة من الموقف — الهدوء يأتي أسرع مع المسافة.",
  ],
  'isolation': [
    "أسمعك وأنا معك الحين بالكامل 💙 الشعور بالوحدة مؤلم جداً — بس أنت حكيت وهذا يعني إنك ما استسلمت. أنا هون.",
    "الوحدة أحياناً تخلينا نحس إننا غير مهمين — بس هذا ليس الحقيقة 💙 أنت مهم/ة وكلامك له قيمة كبيرة.",
    "شعور الوحدة صعب كتير 🌟 هل في نشاط أو هواية بتحبها؟ ملاقاة ناس بنفس الاهتمامات بيبني صداقات حقيقية.",
    "أنا سامع/ة كل كلمة 💙 نفكر سوا بخطوة واحدة ممكن تبدأ فيها اليوم للتواصل مع العالم. حتى خطوة صغيرة تفرق.",
    "إنك حكيت يعني إنك ما استسلمت للوحدة 💜 هل في حدا واحد في المدرسة أو البيت ممكن تفتح معه محادثة بسيطة؟",
    "الشعور بالاغتراب حتى وسط الناس مؤلم جداً 💙 أحياناً المشكلة مو في عدد الناس — بل في عمق التواصل.",
    "ناس كتير يمرون بنفس الإحساس 💙 الصبر والانفتاح الصغير بيصنعان فرقاً كبيراً مع الوقت.",
    "الوحدة ليست نقصاً فيك — أحياناً نحتاج بيئة مختلفة أو ناس مختلفين. هل فكرت بنشاط جديد أو نادي؟",
    "حتى أن تتحدث معي الآن هو شكل من أشكال التواصل 💙 أنت لا تستسلم — هذا يعني الكثير.",
  ],
  'critical': [
    "أنا قلقان/ة عليك كتير من اللي قلته 💙 وبدي أسألك مباشرة بكل محبة: هل أنت بأمان الحين؟ أرجوك اتصل فوراً بـ 911 أو حكي مع حدا بالغ تثق فيه الحين.",
    "اللي قلته أخذ انتباهي بشكل كامل 💙 أنت تستحق المساعدة والدعم الآن وليس غداً. أرجوك اتصل بـ 911 أو توجه فوراً لشخص بالغ.",
    "أسمعك وأنا معك تماماً 💜 الألم الذي تحس فيه حقيقي ومؤلم — لكنه مؤقت وقابل للتحسن. أرجوك لا تواجهه وحدك. رقم الطوارئ: 911.",
    "أنا شايف/ة إنك تمر بألم شديد جداً الحين 💙 وأحب تعرف إن الطريق للأفضل موجود دائماً بالمساعدة المناسبة. اتصل بـ 911 أو اذهب لأقرب شخص بالغ الحين.",
    "ما تقوله يخبرني إنك تحتاج لمساعدة فورية 💙 هذا الألم الشديد يمكن أن يتحسن — لكن تحتاج شخصاً متخصصاً الآن. 911 أو أقرب شخص بالغ موثوق.",
  ],
  'happy': [
    "والله يسعدني جداً إني سمعت هيك! 🌟 شو اللي خلاك تحس بهالسعادة اليوم؟",
    "عظيم إنك بخير ومبسوط! 😊 حكيلي أكثر — شو صار اليوم؟ بدي أشارك معك هذا الفرح!",
    "اللي شاركتني إياه حلو كتير 🌸 الحمد لله على هذا الشعور الرائع. كيف بتحافظ على روحك الإيجابية؟",
    "يسعدني جداً إنك بخير وسعيد/ة 🌟 الأوقات الحلوة نبني فيها ذكريات جميلة. شو المجال اللي تحس فيه بأكثر رضا؟",
    "هذا اللي أحبه 💙 استمر في هذا المزاج الجميل وانشر السعادة حولك! الفرح اللي تشعر به معدي للآخرين.",
    "مبروك على هذا اليوم الجميل! 🎉 ما الذي جعل هذا اليوم خاصاً بالنسبة لك؟",
  ],
  'neutral': [
    "أهلاً وسهلاً 😊 أنا نور. كيف حالك اليوم؟ في شي على بالك بدك تحكيه؟",
    "مرحباً! 👋 أنا هون معك. حكيلي كيف يومك — ما في صح أو غلط، فقط تكلم بصدق.",
    "هلا وغلا! أنا نور وأنا هون أسمعك 🌟 شو عندك اليوم؟",
    "أهلاً 💙 يوم جديد ومعه فرص جديدة. كيف تحس؟",
    "مرحباً بك 🌸 سواء كان يومك عادياً أو صعباً، أنا هون. شو على بالك؟",
    "هلا! أنا سعيد/ة إنك هون 🌟 بتقدر تحكيلي عن يومك أو أي شي يشغل تفكيرك.",
    "أهلاً وسهلاً 🌟 شو تبي تحكي عنه اليوم؟ أنا هون ومعك.",
    "مرحباً! نور معك هون 💙 أخبرني — هل يومك كان جيداً أم تحتاج أن نتحدث عن شيء؟",
  ],
 },
 'en': {
  'bullying': [
    "I hear every word and I'm completely with you 💙 What you're going through is not okay — no one deserves this. Can you tell me more about what happened?",
    "Thank you for trusting me 💙 This is not your fault — it never is. Have you been able to talk to a school counselor or trusted adult?",
    "I'm listening carefully 💙 Bullying must stop. Document what's happening (dates, details) and report it to your counselor. You deserve to feel safe.",
    "What you shared matters and I want to help you think through this. Would you feel comfortable reaching out to a counselor or parent about this?",
    "Staying silent about bullying doesn't make it stop. Your counselor is confidential and there to help. Would you reach out to them?",
    "Cyberbullying is serious and it's not your fault 🛡️ Save evidence, report on the platform, and tell a trusted adult today.",
  ],
  'depression': [
    "Thank you for opening up 💙 The sadness you feel is real and valid. How long have you been feeling this way?",
    "I hear you, and your feelings matter 💜 Depression is not weakness — it can get better with the right support. Have you considered speaking with a counselor?",
    "What you shared touched me deeply 💙 You're not alone. Is there one small thing that might make today a little better?",
    "You're not alone in this, even when it feels that way 💙 Would you be open to talking with your school counselor this week?",
    "I'm proud of you for sharing instead of hiding it. That's the first real step. Your feelings are valid and they can improve.",
    "The numbness you described is a real symptom, not your imagination 💙 It can get better with the right support.",
  ],
  'anxiety': [
    "I hear you 💙 Let's try together: breathe in 4 counts, hold 4, out for 6. Now tell me what's worrying you most.",
    "Anxiety is manageable 💙 Your brain is working overtime to protect you. What triggers your anxiety most?",
    "Try 5-4-3-2-1 grounding: name 5 things you see, 4 touch, 3 hear, 2 smell, 1 taste. This brings you to the present moment.",
    "Breathe with me 🌊 In... hold... out slowly... Anxiety is temporary. What's weighing on you most right now?",
    "Writing down your worries before bed can help empty your mind 💙 Have you tried that?",
  ],
  'critical': [
    "I'm very concerned about what you shared 💙 Are you safe right now? Please call 911 or talk to a trusted adult immediately. You matter.",
    "What you said tells me you need support right now 💜 Please call 911 or go to a trusted adult. This pain can get better with help.",
    "I hear your pain and I care deeply 💙 Please call 911 immediately or tell a trusted adult. You are not alone in this.",
  ],
  'isolation': [
    "I hear you and I'm here with you right now 💙 The loneliness you feel is real. Can you tell me more about it?",
    "Loneliness can make us feel invisible — but you're not. You matter 🌟 Is there one small step you could take to connect today?",
    "The fact that you reached out shows you haven't given up 💙 That matters.",
  ],
  'anger': [
    "Your anger is valid 💙 Let's talk about how to express it in a healthy way that won't hurt you or others.",
    "What happened? Sometimes talking it through reduces the intensity significantly.",
  ],
  'happy': [
    "That's wonderful to hear! 🌟 What made today so special? I'd love to share in your happiness!",
    "I'm so glad you're feeling great! 😊 Hold onto this feeling — these moments are so important.",
  ],
  'neutral': [
    "Hello! I'm Nour 😊 How are you feeling today? What's on your mind?",
    "Hi there! 👋 I'm here for you. Whatever you need to talk about, I'm listening.",
    "Welcome! 🌟 Whether your day is great or tough, I'm here. What would you like to share?",
  ],
 }
}

def get_companion_response(emotion: str, lang: str = 'ar', text: str = '',
                           history: Optional[List[dict]] = None) -> str:
    lang = lang if lang in ('ar', 'en') else 'ar'
    pool = _NOUR.get(lang, _NOUR['ar'])

    em_map = {
        'happy':'happy','joy':'happy','positive':'happy',
        'sad':'depression','sadness':'depression','depressed':'depression',
        'worried':'anxiety','fear':'anxiety','anxious':'anxiety',
        'angry':'anger','anger':'anger',
        'alone':'isolation','lonely':'isolation',
        'critical':'critical','self_harm':'critical',
    }
    emotion = em_map.get(emotion, emotion)
    responses = pool.get(emotion, pool.get('neutral', ['أنا هون معك 💙']))

    # Smart selection: avoid recent responses
    if history:
        recent = {m.get('content','')[:50] for m in history[-8:] if m.get('role')=='assistant'}
        avail = [r for r in responses if r[:50] not in recent]
        if not avail: avail = responses
    else:
        avail = responses

    # Context-aware: check for specific keywords in text for better matching
    text_lower = text.lower() if text else ''
    context_responses = []

    # Greeting detection
    greet_words = ['مرحبا','هلا','السلام','هاي','شلونك','كيفك','hello','hi','hey','how are']
    if any(w in text_lower for w in greet_words) and emotion in ('neutral','happy'):
        greet_pool = pool.get('neutral', avail)
        context_responses = [r for r in greet_pool if r[:50] not in {m.get('content','')[:50] for m in (history or [])[-4:] if m.get('role')=='assistant'}]

    # School/study related
    study_words = ['مدرسة','دراسة','امتحان','معلم','واجب','school','study','exam','teacher','homework','grade']
    if any(w in text_lower for w in study_words) and emotion in ('anxiety','neutral'):
        study_responses_ar = [
            "الدراسة أحياناً بتكون ثقيلة 📚 بس تذكر إن كل جهد بتبذله بيرجعلك. شو بالتحديد عم يضغط عليك؟",
            "ضغط الامتحانات طبيعي جداً 💙 جرب تقسم المادة لأجزاء صغيرة — هيك بتحس إنه أسهل. محتاج نصائح دراسة؟",
            "فاهمك تماماً 📖 المدرسة ممكن تكون مرهقة. بس أنت أقوى من أي امتحان. شو رأيك نحكي عن خطة لتخفيف الضغط؟",
        ]
        study_responses_en = [
            "School pressure is real 📚 But every effort you put in comes back to you. What specifically is stressing you?",
            "Exam stress is totally normal 💙 Try breaking the material into small parts. Need study tips?",
        ]
        extra = study_responses_ar if lang=='ar' else study_responses_en
        context_responses.extend(extra)

    # Family related
    family_words = ['أهل','أمي','أبوي','بيت','عائلة','family','mom','dad','parent','home']
    if any(w in text_lower for w in family_words):
        family_responses_ar = [
            "العلاقة مع الأهل أحياناً بتكون معقدة 💙 بس هم بيحبوك حتى لو ما عبروا بالشكل الصح. شو اللي صار؟",
            "أفهم إن البيت ممكن يكون مصدر ضغط أحياناً 🏠 بدك تحكيلي أكثر؟ أنا هون أسمعك.",
        ]
        family_responses_en = [
            "Family relationships can be complicated 💙 But they love you even if they don't always show it right. What happened?",
        ]
        extra = family_responses_ar if lang=='ar' else family_responses_en
        context_responses.extend(extra)

    # Use context responses if available
    if context_responses:
        if history:
            recent = {m.get('content','')[:50] for m in history[-6:] if m.get('role')=='assistant'}
            context_responses = [r for r in context_responses if r[:50] not in recent]
        if context_responses:
            avail = context_responses

    # Follow-up awareness: if conversation is long, be more personal
    if history and len(history) >= 6:
        followup_ar = [
            "بحب إنك مستمر تحكيلي 💙 هذا يعني إنك شخص واعي لمشاعره. كمّل...",
            "شكراً إنك بتثق فيي وبتشاركني 🌟 أحكيلي أكثر.",
            "محادثتنا مهمة وأنا مستمع بكل اهتمام 💙 شو كمان على بالك؟",
        ]
        followup_en = [
            "I appreciate you continuing to share 💙 It shows real self-awareness. Go on...",
            "Thank you for trusting me with this 🌟 Tell me more.",
        ]
        extra = followup_ar if lang=='ar' else followup_en
        if history:
            recent = {m.get('content','')[:50] for m in history[-4:] if m.get('role')=='assistant'}
            filtered = [r for r in extra if r[:50] not in recent]
            if filtered and random.random() < 0.25:
                avail = filtered + avail[:3]

    # Use hash for consistency + variety
    seed = abs(hash((text[:30] if text else '') + emotion + str(len(history or [])))) % max(len(avail), 1)
    return avail[seed % len(avail)]


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — QUICK CLASSIFY (fast local keyword classifier)
# ══════════════════════════════════════════════════════════════════════════════

_QC_KEYWORDS = {
    "bullying":   ["يضربني","يتنمر","يؤذيني","يهددني","يسخر","يشتمني","يحقرني",
                   "بيضربني","بيأذيني","بيسخر","عم يتنمر","bullied","hit me",
                   "threaten","harass","mock","humiliat","picking on"],
    "depression": ["لا معنى","أكره حياتي","لا أريد أن أعيش","يائس","لا أحد يهتم",
                   "أتمنى الموت","أريد الاختفاء","مكتئب","تعبت من حياتي","بلا أمل",
                   "زهقت","hopeless","hate my life","want to die","worthless","depressed",
                   "بدي أنهي","مو لاقي حالي","حياتي بلا معنى"],
    "anxiety":    ["قلقان","خائف","مرعوب","أرتجف","توتر","مضطرب","وسواس",
                   "هجمة هلع","أفكار لا تتوقف","anxious","panic","terrified",
                   "can't sleep","worried","racing thoughts","خايف","قلبي بيدق"],
    "isolation":  ["وحيد","لا أصدقاء","يتجاهلونني","منبوذ","لا أنتمي","كلهم تركوني",
                   "lonely","no friends","rejected","abandoned","excluded",
                   "دايماً لحالي","ما عندي أصحاب"],
    "physical":   ["تعبان جسمياً","إرهاق","لا أنام","صداع","دوخة","لا أكل",
                   "exhausted","can't sleep","no appetite","headache","fatigue",
                   "جسمي موجوع","محروم من النوم"],
    "positive":   ["سعيد","مبسوط","ممتاز","نجحت","الحمدلله","بخير","فرحان",
                   "happy","great","amazing","grateful","proud","good day",
                   "كويس","منيح","تمام"],
}

_QC_CRITICAL = [
    "أريد الموت","أتمنى الموت","أفكر في الانتحار","أريد أن أقتل نفسي",
    "لا أريد أن أعيش","أريد إيذاء نفسي","بدي أنهي حياتي","تعبت وبدي أنهيها",
    "want to die","kill myself","suicide","want to hurt myself","end my life",
]

def quick_classify(text: str) -> dict:
    """Fast local keyword-based classification."""
    text_lower = text.lower()
    is_crit = any(p in text_lower for p in _QC_CRITICAL)
    scores: dict = {}
    found: dict = {}

    for cat, phrases in _QC_KEYWORDS.items():
        hits = [p for p in phrases if p in text_lower]
        if hits:
            scores[cat] = float(len(hits) * (3.0 if cat in ("bullying", "depression") else 2.0))
            found[cat] = hits

    pos = scores.get("positive", 0)
    neg_c = {c: s for c, s in scores.items() if c != "positive"}

    if is_crit:
        dominant, conf = "depression", 0.95
    elif neg_c:
        dominant = max(neg_c, key=neg_c.get)
        eff = neg_c[dominant] - pos * 0.5
        conf = min(0.85, max(0.35, 0.35 + eff * 0.05))
        if pos > neg_c[dominant] * 1.5:
            dominant, conf = "positive", 0.75
    elif pos > 0:
        dominant, conf = "positive", 0.70
    else:
        dominant, conf = "neutral", 0.55

    is_ar = any("\u0600" <= c <= "\u06FF" for c in text)
    return {
        "lang": "ar" if is_ar else "en",
        "dominant_emotion": dominant,
        "confidence": conf,
        "found_keywords": found,
        "has_bullying": "bullying" in found,
        "negative_hits": sum(len(v) for k, v in found.items() if k != "positive"),
        "weighted_hits": sum(s for k, s in scores.items() if k != "positive"),
        "neg_density": 0,
        "word_count": len(text.split()),
        "category_scores": scores,
        "all_categories": list(found.keys()),
        "is_critical": is_crit,
        "source": "local",
    }
