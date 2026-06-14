"""Mandarin Tutor — curriculum (0 -> conversational) + SQLite persistence.

A structured learning path: Units -> Lessons -> Items. Each item is a word or
short phrase with hanzi, pinyin, English gloss, and the target tone
of its FIRST syllable (used by the /assess pronunciation drill).

The SQLite DB also holds progress + achievements (wired in a later phase), but
the schema is created here so everything lives in one place.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tutor.db")


# ---------------------------------------------------------------------------
# Curriculum content
# ---------------------------------------------------------------------------
# Each item: (hanzi, pinyin, gloss, tone)  -- tone = target tone of 1st syllable
# Lessons are ordered; a learner unlocks the next lesson by completing the
# current one (completion logic lives in the progress phase).

CURRICULUM = [
    {
        "id": "u1",
        "level": "basic",
        "title": "Unit 1 — Greetings & the 4 Tones",
        "desc": "Start from zero: learn the 4 Mandarin tones through greeting words.",
        "lessons": [
            {
                "id": "u1l1",
                "title": "你好 — Hello",
                "goal": "Most basic greeting + feel tones 3 & 2.",
                "items": [
                    ("你", "nǐ", "you (tone 3)", 3),
                    ("好", "hǎo", "good (tone 3)", 3),
                    ("你好", "nǐ hǎo", "hello (tone 3)", 3),
                    ("您", "nín", "you (polite) (tone 2)", 2),
                    ("早", "zǎo", "early / morning (tone 3)", 3),
                    ("早上好", "zǎo shang hǎo", "good morning (tone 3)", 3),
                    ("晚上好", "wǎn shang hǎo", "good evening (tone 3)", 3),
                    ("嗨", "hāi", "hi (tone 1)", 1),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'hello'", "prompt_id": "Ucapkan 'halo'",
                     "answer_hanzi": "你好", "answer_pinyin": "nǐ hǎo"},
                    {"prompt_en": "Say 'good morning'", "prompt_id": "Ucapkan 'selamat pagi'",
                     "answer_hanzi": "早上好", "answer_pinyin": "zǎo shang hǎo"},
                ],
            },
            {
                "id": "u1l2",
                "title": "谢谢 — Thank you",
                "goal": "Polite expressions + tone 4.",
                "items": [
                    ("谢", "xiè", "thanks (tone 4)", 4),
                    ("谢谢", "xiè xie", "thank you (tone 4)", 4),
                    ("不", "bù", "not (tone 4)", 4),
                    ("对不起", "duì bu qǐ", "sorry (tone 4)", 4),
                    ("没关系", "méi guān xi", "no problem (tone 2)", 2),
                    ("请", "qǐng", "please / invite (tone 3)", 3),
                    ("不客气", "bù kè qi", "you're welcome (tone 4)", 4),
                    ("再见", "zài jiàn", "goodbye (tone 4)", 4),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'thank you'", "prompt_id": "Ucapkan 'terima kasih'",
                     "answer_hanzi": "谢谢", "answer_pinyin": "xiè xie"},
                    {"prompt_en": "Say 'sorry'", "prompt_id": "Ucapkan 'maaf'",
                     "answer_hanzi": "对不起", "answer_pinyin": "duì bu qǐ"},
                    {"prompt_en": "Say 'you're welcome'", "prompt_id": "Ucapkan 'sama-sama'",
                     "answer_hanzi": "不客气", "answer_pinyin": "bù kè qi"},
                ],
            },
            {
                "id": "u1l3",
                "title": "妈麻马骂 — 4 Tones",
                "goal": "Classic quartet: 1 syllable 'ma', 4 different tones.",
                "items": [
                    ("妈", "mā", "mother (tone 1)", 1),
                    ("麻", "má", "hemp (tone 2)", 2),
                    ("马", "mǎ", "horse (tone 3)", 3),
                    ("骂", "mà", "scold (tone 4)", 4),
                    ("书", "shū", "book (tone 1)", 1),
                    ("学", "xué", "study (tone 2)", 2),
                    ("买", "mǎi", "buy (tone 3)", 3),
                    ("爱", "ài", "love (tone 4)", 4),
                ],
                "recall_prompts": [
                    {"prompt_en": "Write the word for 'mother'", "prompt_id": "Tulis kata 'ibu'",
                     "answer_hanzi": "妈", "answer_pinyin": "mā"},
                    {"prompt_en": "Write the word for 'book'", "prompt_id": "Tulis kata 'buku'",
                     "answer_hanzi": "书", "answer_pinyin": "shū"},
                ],
            },
        ],
    },
    {
        "id": "u2",
        "level": "basic",
        "title": "Unit 2 — Numbers 1-10",
        "desc": "Basic counting — foundation for prices, time, and age.",
        "lessons": [
            {
                "id": "u2l1",
                "title": "一二三四五 — 1 to 5",
                "goal": "The first five numbers.",
                "items": [
                    ("一", "yī", "one (tone 1)", 1),
                    ("二", "èr", "two (tone 4)", 4),
                    ("三", "sān", "three (tone 1)", 1),
                    ("四", "sì", "four (tone 4)", 4),
                    ("五", "wǔ", "five (tone 3)", 3),
                    ("零", "líng", "zero (tone 2)", 2),
                    ("两", "liǎng", "two (quantity) (tone 3)", 3),
                    ("百", "bǎi", "hundred (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Write the number 'three'", "prompt_id": "Tulis angka 'tiga'",
                     "answer_hanzi": "三", "answer_pinyin": "sān"},
                    {"prompt_en": "Write 'two cups' (quantity)", "prompt_id": "Tulis 'dua gelas' (kuantitas)",
                     "answer_hanzi": "两杯", "answer_pinyin": "liǎng bēi"},
                ],
            },
            {
                "id": "u2l2",
                "title": "六七八九十 — 6 to 10",
                "goal": "The next five numbers.",
                "items": [
                    ("六", "liù", "six (tone 4)", 4),
                    ("七", "qī", "seven (tone 1)", 1),
                    ("八", "bā", "eight (tone 1)", 1),
                    ("九", "jiǔ", "nine (tone 3)", 3),
                    ("十", "shí", "ten (tone 2)", 2),
                    ("十一", "shí yī", "eleven (tone 2)", 2),
                    ("二十", "èr shí", "twenty (tone 4)", 4),
                    ("一百", "yī bǎi", "one hundred (tone 1)", 1),
                ],
                "recall_prompts": [
                    {"prompt_en": "Write the number 'eight'", "prompt_id": "Tulis angka 'delapan'",
                     "answer_hanzi": "八", "answer_pinyin": "bā"},
                    {"prompt_en": "Write 'twenty'", "prompt_id": "Tulis 'dua puluh'",
                     "answer_hanzi": "二十", "answer_pinyin": "èr shí"},
                ],
            },
            {
                "id": "u2l3",
                "title": "数字在情境中 — Numbers in Context",
                "goal": "Use numbers for prices, age, and phone numbers.",
                "items": [
                    ("多少钱", "duō shǎo qián", "how much money (tone 1)", 1),
                    ("一块钱", "yī kuài qián", "one yuan (tone 1)", 1),
                    ("五块", "wǔ kuài", "five yuan (tone 3)", 3),
                    ("我今年二十岁", "wǒ jīn nián èr shí suì", "I am twenty years old (tone 3)", 3),
                    ("几岁", "jǐ suì", "how old (tone 3)", 3),
                    ("岁", "suì", "years old (tone 4)", 4),
                    ("号码", "hào mǎ", "number / phone number (tone 4)", 4),
                    ("电话", "diàn huà", "telephone (tone 4)", 4),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'how much?'", "prompt_id": "Tanyakan 'berapa harganya?'",
                     "answer_hanzi": "多少钱", "answer_pinyin": "duō shǎo qián"},
                    {"prompt_en": "Say 'I am twenty years old'", "prompt_id": "Katakan 'saya berusia dua puluh tahun'",
                     "answer_hanzi": "我今年二十岁", "answer_pinyin": "wǒ jīn nián èr shí suì"},
                ],
            },
        ],
    },
    {
        "id": "u3",
        "level": "basic",
        "title": "Unit 3 — Introducing Yourself",
        "desc": "Talk about your name and origin — your first real conversation.",
        "lessons": [
            {
                "id": "u3l1",
                "title": "我叫… — My name is…",
                "goal": "Say your own name.",
                "items": [
                    ("我", "wǒ", "I (tone 3)", 3),
                    ("叫", "jiào", "called (tone 4)", 4),
                    ("名字", "míng zi", "name (tone 2)", 2),
                    ("我叫", "wǒ jiào", "my name is (tone 3)", 3),
                    ("他", "tā", "he (tone 1)", 1),
                    ("她", "tā", "she (tone 1)", 1),
                    ("我们", "wǒ men", "we (tone 3)", 3),
                    ("你们", "nǐ men", "you all (tone 3)", 3),
                    ("他们", "tā men", "they (tone 1)", 1),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'my name is'", "prompt_id": "Katakan 'nama saya adalah'",
                     "answer_hanzi": "我叫", "answer_pinyin": "wǒ jiào"},
                    {"prompt_en": "Say 'we'", "prompt_id": "Katakan 'kami'",
                     "answer_hanzi": "我们", "answer_pinyin": "wǒ men"},
                ],
            },
            {
                "id": "u3l2",
                "title": "你是哪国人 — Where are you from",
                "goal": "Ask and answer where someone is from.",
                "items": [
                    ("是", "shì", "to be (tone 4)", 4),
                    ("人", "rén", "person (tone 2)", 2),
                    ("中国", "zhōng guó", "China (tone 1)", 1),
                    ("印尼", "yìn ní", "Indonesia (tone 4)", 4),
                    ("哪国", "nǎ guó", "which country (tone 3)", 3),
                    ("美国", "měi guó", "USA (tone 3)", 3),
                    ("日本", "rì běn", "Japan (tone 4)", 4),
                    ("韩国", "hán guó", "Korea (tone 2)", 2),
                    ("哪里", "nǎ lǐ", "where (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'where are you from?'", "prompt_id": "Tanyakan 'kamu dari mana?'",
                     "answer_hanzi": "你是哪国人", "answer_pinyin": "nǐ shì nǎ guó rén"},
                    {"prompt_en": "Say 'I am Indonesian'", "prompt_id": "Katakan 'saya orang Indonesia'",
                     "answer_hanzi": "我是印尼人", "answer_pinyin": "wǒ shì yìn ní rén"},
                ],
            },
            {
                "id": "u3l3",
                "title": "完整自我介绍 — Full Self-Introduction",
                "goal": "Capstone: say a whole self-introduction. Pass this to unlock Intermediate.",
                "capstone": True,
                "items": [
                    ("你好", "nǐ hǎo", "hello", 3),
                    ("很高兴", "hěn gāo xìng", "very glad", 3),
                    ("认识你", "rèn shi nǐ", "to meet you (tone 4)", 4),
                    ("我叫", "wǒ jiào", "my name is", 3),
                    ("我来自", "wǒ lái zì", "I come from (tone 3)", 3),
                    ("印度尼西亚", "yìn dù ní xī yà", "Indonesia", 4),
                    ("我是学生", "wǒ shì xué shēng", "I am a student (tone 3)", 3),
                    ("很高兴认识你", "hěn gāo xìng rèn shi nǐ", "nice to meet you (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'nice to meet you'", "prompt_id": "Katakan 'senang bertemu denganmu'",
                     "answer_hanzi": "很高兴认识你", "answer_pinyin": "hěn gāo xìng rèn shi nǐ"},
                    {"prompt_en": "Say 'I come from Indonesia'", "prompt_id": "Katakan 'saya berasal dari Indonesia'",
                     "answer_hanzi": "我来自印度尼西亚", "answer_pinyin": "wǒ lái zì yìn dù ní xī yà"},
                ],
            },
        ],
    },
    {
        "id": "u4",
        "level": "intermediate",
        "title": "Unit 4 — Everyday Phrases",
        "desc": "Short useful sentences for daily situations.",
        "unlock_after": "u3l3",
        "lessons": [
            {
                "id": "u4l1",
                "title": "你好吗 — How are you",
                "goal": "Ask and answer about wellbeing.",
                "items": [
                    ("吗", "ma", "(question particle)", 5),
                    ("很好", "hěn hǎo", "very good (tone 3)", 3),
                    ("不错", "bú cuò", "not bad (tone 2)", 2),
                    ("你呢", "nǐ ne", "and you? (tone 3)", 3),
                    ("还好", "hái hǎo", "so-so / still fine (tone 2)", 2),
                    ("一般", "yī bān", "average / ordinary (tone 1)", 1),
                    ("累", "lèi", "tired (tone 4)", 4),
                    ("高兴", "gāo xìng", "happy (tone 1)", 1),
                    ("难过", "nán guò", "sad (tone 2)", 2),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'how are you?'", "prompt_id": "Tanyakan 'apa kabar?'",
                     "answer_hanzi": "你好吗", "answer_pinyin": "nǐ hǎo ma"},
                    {"prompt_en": "Say 'I am very happy'", "prompt_id": "Katakan 'saya sangat senang'",
                     "answer_hanzi": "我很高兴", "answer_pinyin": "wǒ hěn gāo xìng"},
                ],
            },
            {
                "id": "u4l2",
                "title": "多少钱 — How much",
                "goal": "Ask prices when shopping.",
                "items": [
                    ("多少", "duō shǎo", "how many (tone 1)", 1),
                    ("钱", "qián", "money (tone 2)", 2),
                    ("贵", "guì", "expensive (tone 4)", 4),
                    ("便宜", "pián yi", "cheap (tone 2)", 2),
                    ("买", "mǎi", "buy (tone 3)", 3),
                    ("卖", "mài", "sell (tone 4)", 4),
                    ("要", "yào", "want / need (tone 4)", 4),
                    ("不要", "bù yào", "don't want (tone 4)", 4),
                    ("给我", "gěi wǒ", "give me (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'how much is this?'", "prompt_id": "Tanyakan 'berapa harga ini?'",
                     "answer_hanzi": "这个多少钱", "answer_pinyin": "zhè ge duō shǎo qián"},
                    {"prompt_en": "Say 'too expensive'", "prompt_id": "Katakan 'terlalu mahal'",
                     "answer_hanzi": "太贵了", "answer_pinyin": "tài guì le"},
                ],
            },
            {
                "id": "u4l3",
                "title": "在哪里 — Where is it",
                "goal": "Ask for and give locations.",
                "items": [
                    ("哪里", "nǎ lǐ", "where (tone 3)", 3),
                    ("这里", "zhè lǐ", "here (tone 4)", 4),
                    ("那里", "nà lǐ", "there (tone 4)", 4),
                    ("厕所", "cè suǒ", "toilet (tone 4)", 4),
                    ("左边", "zuǒ biān", "left side (tone 3)", 3),
                    ("右边", "yòu biān", "right side (tone 4)", 4),
                    ("前面", "qián miàn", "in front (tone 2)", 2),
                    ("后面", "hòu miàn", "behind (tone 4)", 4),
                    ("旁边", "páng biān", "beside / next to (tone 2)", 2),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'where is the toilet?'", "prompt_id": "Tanyakan 'di mana toilet?'",
                     "answer_hanzi": "厕所在哪里", "answer_pinyin": "cè suǒ zài nǎ lǐ"},
                    {"prompt_en": "Say 'turn left'", "prompt_id": "Katakan 'belok kiri'",
                     "answer_hanzi": "往左边走", "answer_pinyin": "wǎng zuǒ biān zǒu"},
                ],
            },
        ],
    },
    {
        "id": "u5",
        "level": "hard",
        "title": "Unit 5 — Real Conversations",
        "desc": "Longer sentences and tone changes in connected speech.",
        "unlock_after": "u4l3",
        "lessons": [
            {
                "id": "u5l1",
                "title": "我想要 — I would like",
                "goal": "Order food and make requests politely.",
                "items": [
                    ("我想要", "wǒ xiǎng yào", "I would like (tone 3)", 3),
                    ("一杯", "yì bēi", "a cup of (tone 4)", 4),
                    ("咖啡", "kā fēi", "coffee (tone 1)", 1),
                    ("谢谢你", "xiè xie nǐ", "thank you (tone 4)", 4),
                    ("吃饭", "chī fàn", "eat (a meal) (tone 1)", 1),
                    ("喝水", "hē shuǐ", "drink water (tone 1)", 1),
                    ("菜单", "cài dān", "menu (tone 4)", 4),
                    ("好吃", "hǎo chī", "delicious (tone 3)", 3),
                    ("不辣", "bù là", "not spicy (tone 4)", 4),
                    ("再来一杯", "zài lái yì bēi", "one more cup (tone 4)", 4),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'I would like a cup of coffee'",
                     "prompt_id": "Katakan 'saya ingin secangkir kopi'",
                     "answer_hanzi": "我想要一杯咖啡", "answer_pinyin": "wǒ xiǎng yào yì bēi kā fēi"},
                    {"prompt_en": "Say 'this is delicious'",
                     "prompt_id": "Katakan 'ini enak'",
                     "answer_hanzi": "这个很好吃", "answer_pinyin": "zhè ge hěn hǎo chī"},
                ],
            },
            {
                "id": "u5l2",
                "title": "现在几点 — What time is it",
                "goal": "Tell and ask the time.",
                "items": [
                    ("现在", "xiàn zài", "now (tone 4)", 4),
                    ("几点", "jǐ diǎn", "what time (tone 3)", 3),
                    ("分钟", "fēn zhōng", "minute (tone 1)", 1),
                    ("半", "bàn", "half (tone 4)", 4),
                    ("上午", "shàng wǔ", "morning / AM (tone 4)", 4),
                    ("下午", "xià wǔ", "afternoon / PM (tone 4)", 4),
                    ("早上", "zǎo shang", "morning (tone 3)", 3),
                    ("晚上", "wǎn shang", "evening (tone 3)", 3),
                    ("时间", "shí jiān", "time (tone 2)", 2),
                    ("等一下", "děng yī xià", "wait a moment (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'what time is it now?'",
                     "prompt_id": "Tanyakan 'sekarang jam berapa?'",
                     "answer_hanzi": "现在几点", "answer_pinyin": "xiàn zài jǐ diǎn"},
                    {"prompt_en": "Say 'it is half past three in the afternoon'",
                     "prompt_id": "Katakan 'sekarang pukul setengah empat sore'",
                     "answer_hanzi": "下午三点半", "answer_pinyin": "xià wǔ sān diǎn bàn"},
                ],
            },
            {
                "id": "u5l3",
                "title": "完整对话 — Full Conversation",
                "goal": "Capstone: a full self-intro + small talk sentence.",
                "capstone": True,
                "items": [
                    ("很高兴认识你", "hěn gāo xìng rèn shi nǐ", "nice to meet you", 3),
                    ("我是学生", "wǒ shì xué shēng", "I am a student (tone 3)", 3),
                    ("我会说一点中文", "wǒ huì shuō yì diǎn zhōng wén", "I can speak a little Chinese", 3),
                    ("再见", "zài jiàn", "goodbye (tone 4)", 4),
                    ("下次见", "xià cì jiàn", "see you next time (tone 4)", 4),
                    ("保持联系", "bǎo chí lián xì", "keep in touch (tone 3)", 3),
                    ("有空来找我", "yǒu kòng lái zhǎo wǒ", "come find me when free (tone 3)", 3),
                    ("很开心跟你聊天", "hěn kāi xīn gēn nǐ liáo tiān", "happy chatting with you (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'I can speak a little Chinese'",
                     "prompt_id": "Katakan 'saya bisa berbicara sedikit Mandarin'",
                     "answer_hanzi": "我会说一点中文", "answer_pinyin": "wǒ huì shuō yì diǎn zhōng wén"},
                    {"prompt_en": "Say 'see you next time'",
                     "prompt_id": "Katakan 'sampai jumpa lagi'",
                     "answer_hanzi": "下次见", "answer_pinyin": "xià cì jiàn"},
                ],
            },
        ],
    },
    {
        "id": "u6",
        "level": "intermediate",
        "title": "Unit 6 — Daily Life",
        "desc": "Navigate family, food, and transport in everyday Mandarin.",
        "unlock_after": "u5l3",
        "lessons": [
            {
                "id": "u6l1",
                "title": "家人 — Family",
                "goal": "Name immediate family members and talk about relationships.",
                "items": [
                    ("家", "jiā", "home / family (tone 1)", 1),
                    ("爸爸", "bà ba", "father (tone 4)", 4),
                    ("妈妈", "mā ma", "mother (tone 1)", 1),
                    ("哥哥", "gē ge", "older brother (tone 1)", 1),
                    ("姐姐", "jiě jie", "older sister (tone 3)", 3),
                    ("弟弟", "dì di", "younger brother (tone 4)", 4),
                    ("妹妹", "mèi mei", "younger sister (tone 4)", 4),
                    ("朋友", "péng yǒu", "friend (tone 2)", 2),
                    ("同学", "tóng xué", "classmate (tone 2)", 2),
                    ("老师", "lǎo shī", "teacher (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'my father'", "prompt_id": "Katakan 'ayah saya'",
                     "answer_hanzi": "我爸爸", "answer_pinyin": "wǒ bà ba"},
                    {"prompt_en": "Say 'my friend'", "prompt_id": "Katakan 'teman saya'",
                     "answer_hanzi": "我的朋友", "answer_pinyin": "wǒ de péng yǒu"},
                    {"prompt_en": "Say 'my teacher is very good'",
                     "prompt_id": "Katakan 'guru saya sangat baik'",
                     "answer_hanzi": "我的老师很好", "answer_pinyin": "wǒ de lǎo shī hěn hǎo"},
                ],
            },
            {
                "id": "u6l2",
                "title": "吃饭点菜 — Ordering Food",
                "goal": "Order food at a restaurant.",
                "items": [
                    ("饭店", "fàn diàn", "restaurant (tone 4)", 4),
                    ("服务员", "fú wù yuán", "waiter (tone 2)", 2),
                    ("点菜", "diǎn cài", "order food (tone 3)", 3),
                    ("米饭", "mǐ fàn", "rice (tone 3)", 3),
                    ("面条", "miàn tiáo", "noodles (tone 4)", 4),
                    ("鸡肉", "jī ròu", "chicken (tone 1)", 1),
                    ("猪肉", "zhū ròu", "pork (tone 1)", 1),
                    ("蔬菜", "shū cài", "vegetables (tone 1)", 1),
                    ("水果", "shuǐ guǒ", "fruit (tone 3)", 3),
                    ("结账", "jié zhàng", "pay the bill (tone 2)", 2),
                ],
                "recall_prompts": [
                    {"prompt_en": "Call the waiter", "prompt_id": "Panggil pelayan",
                     "answer_hanzi": "服务员", "answer_pinyin": "fú wù yuán"},
                    {"prompt_en": "Say 'I want to order'", "prompt_id": "Katakan 'saya ingin memesan'",
                     "answer_hanzi": "我要点菜", "answer_pinyin": "wǒ yào diǎn cài"},
                    {"prompt_en": "Ask for the bill", "prompt_id": "Minta tagihan",
                     "answer_hanzi": "请结账", "answer_pinyin": "qǐng jié zhàng"},
                ],
            },
            {
                "id": "u6l3",
                "title": "出行 — Getting Around",
                "goal": "Capstone: use transport and ask for directions.",
                "capstone": True,
                "items": [
                    ("地铁", "dì tiě", "subway (tone 4)", 4),
                    ("公共汽车", "gōng gòng qì chē", "bus (tone 1)", 1),
                    ("出租车", "chū zū chē", "taxi (tone 1)", 1),
                    ("机场", "jī chǎng", "airport (tone 1)", 1),
                    ("火车站", "huǒ chē zhàn", "train station (tone 3)", 3),
                    ("怎么走", "zěn me zǒu", "how to get there (tone 3)", 3),
                    ("走路", "zǒu lù", "walk (tone 3)", 3),
                    ("多远", "duō yuǎn", "how far (tone 1)", 1),
                    ("需要多长时间", "xū yào duō cháng shí jiān", "how long does it take (tone 1)", 1),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'how do I get to the train station?'",
                     "prompt_id": "Tanyakan 'bagaimana cara ke stasiun kereta?'",
                     "answer_hanzi": "火车站怎么走", "answer_pinyin": "huǒ chē zhàn zěn me zǒu"},
                    {"prompt_en": "Ask 'how far is it?'", "prompt_id": "Tanyakan 'seberapa jauh?'",
                     "answer_hanzi": "有多远", "answer_pinyin": "yǒu duō yuǎn"},
                ],
            },
        ],
    },
    {
        "id": "u7",
        "level": "hard",
        "title": "Unit 7 — Stories & Opinions",
        "desc": "Express opinions, recount events, and hold real multi-turn conversations.",
        "unlock_after": "u6l3",
        "lessons": [
            {
                "id": "u7l1",
                "title": "观点与感受 — Opinions & Feelings",
                "goal": "Express what you think and feel about topics.",
                "items": [
                    ("觉得", "jué de", "feel / think (tone 2)", 2),
                    ("认为", "rèn wéi", "believe / consider (tone 4)", 4),
                    ("喜欢", "xǐ huān", "like (tone 3)", 3),
                    ("不喜欢", "bù xǐ huān", "don't like (tone 4)", 4),
                    ("有意思", "yǒu yì si", "interesting (tone 3)", 3),
                    ("没意思", "méi yì si", "boring (tone 2)", 2),
                    ("重要", "zhòng yào", "important (tone 4)", 4),
                    ("担心", "dān xīn", "worry (tone 1)", 1),
                    ("希望", "xī wàng", "hope (tone 1)", 1),
                    ("同意", "tóng yì", "agree (tone 2)", 2),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'I think this is interesting'",
                     "prompt_id": "Katakan 'saya pikir ini menarik'",
                     "answer_hanzi": "我觉得这个很有意思",
                     "answer_pinyin": "wǒ jué de zhè ge hěn yǒu yì si"},
                    {"prompt_en": "Say 'I like Mandarin'",
                     "prompt_id": "Katakan 'saya suka bahasa Mandarin'",
                     "answer_hanzi": "我喜欢中文", "answer_pinyin": "wǒ xǐ huān zhōng wén"},
                ],
            },
            {
                "id": "u7l2",
                "title": "日常生活 — Daily Routine",
                "goal": "Recount past events and describe daily activities.",
                "items": [
                    ("昨天", "zuó tiān", "yesterday (tone 2)", 2),
                    ("今天", "jīn tiān", "today (tone 1)", 1),
                    ("明天", "míng tiān", "tomorrow (tone 2)", 2),
                    ("上班", "shàng bān", "go to work (tone 4)", 4),
                    ("下班", "xià bān", "get off work (tone 4)", 4),
                    ("睡觉", "shuì jiào", "sleep (tone 4)", 4),
                    ("起床", "qǐ chuáng", "get up (tone 3)", 3),
                    ("锻炼", "duàn liàn", "exercise (tone 4)", 4),
                    ("看书", "kàn shū", "read a book (tone 4)", 4),
                    ("已经", "yǐ jīng", "already (tone 3)", 3),
                ],
                "recall_prompts": [
                    {"prompt_en": "Say 'I already went to work yesterday'",
                     "prompt_id": "Katakan 'kemarin saya sudah pergi kerja'",
                     "answer_hanzi": "我昨天已经上班了",
                     "answer_pinyin": "wǒ zuó tiān yǐ jīng shàng bān le"},
                    {"prompt_en": "Say 'I wake up at 7 every day'",
                     "prompt_id": "Katakan 'setiap hari saya bangun jam 7'",
                     "answer_hanzi": "我每天七点起床",
                     "answer_pinyin": "wǒ měi tiān qī diǎn qǐ chuáng"},
                ],
            },
            {
                "id": "u7l3",
                "title": "综合对话 — Full Conversational Range",
                "goal": "Capstone: hold a multi-turn conversation on any daily topic.",
                "capstone": True,
                "items": [
                    ("最近怎么样", "zuì jìn zěn me yàng", "how have you been lately (tone 4)", 4),
                    ("还不错", "hái bú cuò", "pretty good (tone 2)", 2),
                    ("工作很忙", "gōng zuò hěn máng", "work is very busy (tone 1)", 1),
                    ("有时间的话", "yǒu shí jiān de huà", "if you have time (tone 3)", 3),
                    ("一起去吃饭吧", "yī qǐ qù chī fàn ba", "let's go eat together (tone 1)", 1),
                    ("好主意", "hǎo zhǔ yi", "good idea (tone 3)", 3),
                    ("我请客", "wǒ qǐng kè", "my treat (tone 3)", 3),
                    ("下次换你请", "xià cì huàn nǐ qǐng", "next time it's your turn (tone 4)", 4),
                ],
                "recall_prompts": [
                    {"prompt_en": "Ask 'how have you been lately?'",
                     "prompt_id": "Tanyakan 'apa kabar belakangan ini?'",
                     "answer_hanzi": "最近怎么样", "answer_pinyin": "zuì jìn zěn me yàng"},
                    {"prompt_en": "Say 'let's go eat together'",
                     "prompt_id": "Katakan 'ayo pergi makan bersama'",
                     "answer_hanzi": "一起去吃饭吧", "answer_pinyin": "yī qǐ qù chī fàn ba"},
                    {"prompt_en": "Say 'my treat'",
                     "prompt_id": "Katakan 'saya yang traktir'",
                     "answer_hanzi": "我请客", "answer_pinyin": "wǒ qǐng kè"},
                ],
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Curriculum access helpers
# ---------------------------------------------------------------------------

def curriculum_outline() -> list[dict]:
    """Units + lessons without item bodies (for the lesson-list screen)."""
    out = []
    for unit in CURRICULUM:
        out.append({
            "id": unit["id"],
            "level": unit.get("level", "basic"),
            "title": unit["title"],
            "desc": unit["desc"],
            "unlock_after": unit.get("unlock_after"),
            "lessons": [
                {
                    "id": l["id"],
                    "title": l["title"],
                    "goal": l["goal"],
                    "count": len(l["items"]),
                    "capstone": l.get("capstone", False),
                    "has_recall_prompts": bool(l.get("recall_prompts")),
                    "recall_prompt_count": len(l.get("recall_prompts", [])),
                }
                for l in unit["lessons"]
            ],
        })
    return out


def get_lesson(lesson_id: str) -> dict | None:
    """Full lesson with items expanded to dicts."""
    for unit in CURRICULUM:
        for l in unit["lessons"]:
            if l["id"] == lesson_id:
                return {
                    "id": l["id"],
                    "title": l["title"],
                    "goal": l["goal"],
                    "unit_id": unit["id"],
                    "unit_title": unit["title"],
                    "items": [
                        {"hanzi": hz, "pinyin": py, "gloss": gl, "tone": tn}
                        for (hz, py, gl, tn) in l["items"]
                    ],
                }
    return None


def all_lesson_ids() -> list[str]:
    """Flat ordered list of every lesson id (used for unlock ordering)."""
    ids = []
    for unit in CURRICULUM:
        for l in unit["lessons"]:
            ids.append(l["id"])
    return ids


# ---------------------------------------------------------------------------
# SQLite persistence (progress + achievements)
# ---------------------------------------------------------------------------

@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if missing. Safe to call on every startup."""
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lesson_progress (
                user_id    TEXT NOT NULL DEFAULT 'default',
                lesson_id  TEXT NOT NULL,
                completed  INTEGER NOT NULL DEFAULT 0,
                best_avg   INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, lesson_id)
            );

            CREATE TABLE IF NOT EXISTS attempts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   TEXT NOT NULL DEFAULT 'default',
                lesson_id TEXT,
                hanzi     TEXT,
                target_tone INTEGER,
                score     INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS writing_attempts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL DEFAULT 'default',
                lesson_id   TEXT,
                hanzi       TEXT,
                mode        TEXT,            -- 'trace' | 'recall'
                score       INTEGER,         -- 0..100 stroke accuracy
                mistakes    INTEGER,         -- total wrong strokes
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS achievements (
                user_id   TEXT NOT NULL DEFAULT 'default',
                badge     TEXT NOT NULL,
                earned_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, badge)
            );

            CREATE TABLE IF NOT EXISTS streak (
                user_id   TEXT PRIMARY KEY DEFAULT 'default',
                current   INTEGER NOT NULL DEFAULT 0,
                longest   INTEGER NOT NULL DEFAULT 0,
                last_day  TEXT
            );
            """
        )


# ---------------------------------------------------------------------------
# Progress / streak / achievements
# ---------------------------------------------------------------------------

# Badges: id -> (label, description). Earned when the predicate in award logic holds.
# Writing "pass" threshold (stroke accuracy). Slightly lower than tone PASS_SCORE
# because correct stroke order at 65+ already means the character is recognisable.
WRITE_PASS_SCORE = 65

BADGES = {
    "first_word":   ("🎤 First Word", "Scored your first pronunciation."),
    "perfect_tone": ("🎯 Perfect Tone", "Got 90+ on a single word."),
    "lesson_done":  ("📘 Lesson Complete", "Finished a full lesson."),
    "ten_attempts": ("🔥 Dedicated", "Practiced 10 times."),
    "streak_3":     ("📅 3-Day Streak", "Practiced 3 days in a row."),
}


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def record_attempt(hanzi: str, target_tone: int, score: int,
                   lesson_id: str | None = None, user_id: str = "default") -> dict:
    """Persist one drill attempt, bump streak, award badges. Returns new badges."""
    with db() as conn:
        conn.execute(
            "INSERT INTO attempts (user_id, lesson_id, hanzi, target_tone, score) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, lesson_id, hanzi, target_tone, score),
        )
        new_badges = _update_streak_and_badges(conn, user_id, score)
    return {"new_badges": new_badges}


def record_writing_attempt(hanzi: str, mode: str, score: int, mistakes: int = 0,
                           lesson_id: str | None = None, user_id: str = "default") -> dict:
    """Persist one writing (stroke) attempt. Bumps streak like the tone drill."""
    mode = "recall" if mode == "recall" else "trace"
    with db() as conn:
        conn.execute(
            "INSERT INTO writing_attempts (user_id, lesson_id, hanzi, mode, score, mistakes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, lesson_id, hanzi, mode, score, mistakes),
        )
        new_badges = _update_streak_and_badges(conn, user_id, score)
    return {"new_badges": new_badges}


def _update_streak_and_badges(conn, user_id: str, score: int) -> list[dict]:
    today = _today()
    row = conn.execute(
        "SELECT current, longest, last_day FROM streak WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        cur, longest, last = 1, 1, today
    else:
        last = row["last_day"]
        if last == today:
            cur, longest = row["current"], row["longest"]
        else:
            yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
            cur = row["current"] + 1 if last == yesterday else 1
            longest = max(row["longest"], cur)
            last = today
    conn.execute(
        "INSERT INTO streak (user_id, current, longest, last_day) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET current=?, longest=?, last_day=?",
        (user_id, cur, longest, last, cur, longest, last),
    )

    earned = {r["badge"] for r in conn.execute(
        "SELECT badge FROM achievements WHERE user_id = ?", (user_id,)).fetchall()}
    total = conn.execute(
        "SELECT COUNT(*) c FROM attempts WHERE user_id = ?", (user_id,)).fetchone()["c"]

    to_award = []
    if "first_word" not in earned and total >= 1:
        to_award.append("first_word")
    if "perfect_tone" not in earned and score >= 90:
        to_award.append("perfect_tone")
    if "ten_attempts" not in earned and total >= 10:
        to_award.append("ten_attempts")
    if "streak_3" not in earned and cur >= 3:
        to_award.append("streak_3")

    new_badges = []
    for b in to_award:
        conn.execute(
            "INSERT OR IGNORE INTO achievements (user_id, badge) VALUES (?, ?)",
            (user_id, b))
        label, desc = BADGES[b]
        new_badges.append({"id": b, "label": label, "desc": desc})
    return new_badges


def complete_lesson(lesson_id: str, best_avg: int, user_id: str = "default") -> dict:
    """Mark a lesson complete; award lesson_done badge on first completion."""
    with db() as conn:
        conn.execute(
            "INSERT INTO lesson_progress (user_id, lesson_id, completed, best_avg, updated_at) "
            "VALUES (?, ?, 1, ?, datetime('now')) "
            "ON CONFLICT(user_id, lesson_id) DO UPDATE SET completed=1, "
            "best_avg=MAX(best_avg, ?), updated_at=datetime('now')",
            (user_id, lesson_id, best_avg, best_avg),
        )
        earned = {r["badge"] for r in conn.execute(
            "SELECT badge FROM achievements WHERE user_id = ?", (user_id,)).fetchall()}
        new_badges = []
        if "lesson_done" not in earned:
            conn.execute(
                "INSERT OR IGNORE INTO achievements (user_id, badge) VALUES (?, 'lesson_done')",
                (user_id,))
            label, desc = BADGES["lesson_done"]
            new_badges.append({"id": "lesson_done", "label": label, "desc": desc})
    return {"new_badges": new_badges}


def lesson_writing_scores(lesson_id: str, user_id: str = "default") -> dict:
    """Best WRITING score per syllable for a lesson + completion stats.

    Mirrors lesson_item_scores but reads writing_attempts. A syllable is
    'passed' for writing at score >= WRITE_PASS_SCORE.
    """
    lesson = get_lesson(lesson_id)
    if lesson is None:
        return {"scores": {}, "items_total": 0, "items_passed": 0,
                "best_avg": 0, "all_passed": False}
    with db() as conn:
        rows = conn.execute(
            "SELECT hanzi, MAX(score) best FROM writing_attempts "
            "WHERE user_id = ? AND lesson_id = ? GROUP BY hanzi",
            (user_id, lesson_id)).fetchall()
    best = {r["hanzi"]: r["best"] for r in rows}
    items = [it["hanzi"] for it in lesson["items"]]
    scores = {hz: best.get(hz, 0) for hz in items}
    passed = [hz for hz in items if scores[hz] >= WRITE_PASS_SCORE]
    vals = list(scores.values())
    best_avg = round(sum(vals) / len(vals)) if vals else 0
    return {
        "scores": scores,
        "items_total": len(items),
        "items_passed": len(passed),
        "best_avg": best_avg,
        "all_passed": len(passed) == len(items) and len(items) > 0,
    }


def lesson_item_scores(lesson_id: str, user_id: str = "default") -> dict:
    """Best score per syllable (hanzi) for a lesson + derived completion stats.

    Returns:
      { scores: {hanzi: best_score}, items_total, items_passed,
        best_avg, all_passed }
    where items_passed counts syllables whose best score >= tone_engine.PASS_SCORE.
    """
    import tone as tone_engine
    lesson = get_lesson(lesson_id)
    if lesson is None:
        return {"scores": {}, "items_total": 0, "items_passed": 0,
                "best_avg": 0, "all_passed": False}
    with db() as conn:
        rows = conn.execute(
            "SELECT hanzi, MAX(score) best FROM attempts "
            "WHERE user_id = ? AND lesson_id = ? GROUP BY hanzi",
            (user_id, lesson_id)).fetchall()
    best = {r["hanzi"]: r["best"] for r in rows}
    items = [it["hanzi"] for it in lesson["items"]]
    scores = {hz: best.get(hz, 0) for hz in items}
    passed = [hz for hz in items if scores[hz] >= tone_engine.PASS_SCORE]
    vals = list(scores.values())
    best_avg = round(sum(vals) / len(vals)) if vals else 0
    return {
        "scores": scores,
        "items_total": len(items),
        "items_passed": len(passed),
        "best_avg": best_avg,
        "all_passed": len(passed) == len(items) and len(items) > 0,
    }


def curriculum_status(user_id: str = "default") -> list[dict]:
    """Curriculum outline annotated with per-lesson progress + unlock state.

    A unit is locked until the lesson named in its `unlock_after` is fully
    passed (every syllable >= PASS_SCORE). Basic units (no unlock_after) are
    always open.
    """
    outline = curriculum_outline()
    for unit in outline:
        gate = unit.get("unlock_after")
        unit["locked"] = bool(gate) and not lesson_item_scores(gate, user_id)["all_passed"]
        for l in unit["lessons"]:
            st = lesson_item_scores(l["id"], user_id)
            l["best_avg"] = st["best_avg"]
            l["items_passed"] = st["items_passed"]
            l["items_total"] = st["items_total"]
            l["all_passed"] = st["all_passed"]
    return outline


def progress_summary(user_id: str = "default") -> dict:
    """Everything the UI needs: streak, totals, done lessons, badges."""
    with db() as conn:
        srow = conn.execute(
            "SELECT current, longest, last_day FROM streak WHERE user_id = ?",
            (user_id,)).fetchone()
        total = conn.execute(
            "SELECT COUNT(*) c FROM attempts WHERE user_id = ?", (user_id,)).fetchone()["c"]
        avg = conn.execute(
            "SELECT AVG(score) a FROM attempts WHERE user_id = ?", (user_id,)).fetchone()["a"]
        done = [r["lesson_id"] for r in conn.execute(
            "SELECT lesson_id FROM lesson_progress WHERE user_id = ? AND completed = 1",
            (user_id,)).fetchall()]
        badge_ids = [r["badge"] for r in conn.execute(
            "SELECT badge FROM achievements WHERE user_id = ? ORDER BY earned_at",
            (user_id,)).fetchall()]
    badges = [{"id": b, "label": BADGES[b][0], "desc": BADGES[b][1]}
              for b in badge_ids if b in BADGES]
    return {
        "streak": {"current": srow["current"] if srow else 0,
                   "longest": srow["longest"] if srow else 0,
                   "last_day": srow["last_day"] if srow else None},
        "total_attempts": total,
        "avg_score": round(avg) if avg is not None else 0,
        "done_lessons": done,
        "badges": badges,
        "all_badges": [{"id": k, "label": v[0], "desc": v[1]} for k, v in BADGES.items()],
    }
