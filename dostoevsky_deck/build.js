const pptxgen = require("pptxgenjs");

// Darker mood palette (matches generate-art.js)
const DARK = "1C1013";   // near-black maroon — primary background
const PANEL = "2E1620";  // deep maroon — cards / side panels
const PANEL2 = "3A2029"; // slightly lighter panel
const BERRY = "9B3D57";
const ROSE = "C08B92";
const CREAM = "E9D9CC";
const GLOW = "F0C08A";
const WHITE = "FFFFFF";
const MUTED = "8A6E7A";

const TITLE_FONT = "Cambria";
const BODY_FONT = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5 in

function darkBg(slide) {
  slide.background = { color: DARK };
}
function pageNum(slide, n) {
  slide.addText(String(n), {
    x: 12.6, y: 7.1, w: 0.5, h: 0.3,
    fontFace: BODY_FONT, fontSize: 10, color: MUTED,
    align: "right", isTextBox: true, margin: 0,
  });
}
function kicker(slide, text, x, y, color) {
  slide.addText(text.toUpperCase(), {
    x, y, w: 8, h: 0.4, isTextBox: true, margin: 0,
    fontFace: BODY_FONT, fontSize: 13, color, bold: true, charSpacing: 3,
  });
}

// ---------- Slide 1: Title ----------
{
  const s = pres.addSlide();
  darkBg(s);
  s.addImage({ path: "art-portrait.png", x: 7.3, y: 0, w: 6.03, h: 7.5, sizing: { type: "cover", w: 6.03, h: 7.5 } });
  s.addShape("rect", { x: 0, y: 0, w: 7.5, h: 7.5, fill: { color: DARK }, line: { type: "none" } });
  s.addShape("rect", { x: 7.3, y: 0, w: 0.5, h: 7.5, fill: { color: DARK, transparency: 55 }, line: { type: "none" } });

  kicker(s, "Литературный вечер", 0.8, 2.05, ROSE);
  s.addText("Достоевский:\nчеловек против закона", {
    x: 0.75, y: 2.5, w: 6.4, h: 2.6, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 42, color: WHITE, bold: true, lineSpacingMultiple: 1.05,
  });
  s.addText("От раннего Достоевского до «Великого инквизитора»: разговор о морали, свободе и цене выбора", {
    x: 0.8, y: 5.3, w: 6.3, h: 1.1, isTextBox: true, margin: 0,
    fontFace: BODY_FONT, fontSize: 15, color: CREAM, italic: true,
  });
  s.addText("Портрет Ф. М. Достоевского. В. Перов, 1872", {
    x: 7.5, y: 7.12, w: 5.6, h: 0.3, isTextBox: true, margin: 0,
    fontFace: BODY_FONT, fontSize: 9, color: "6E5A62", italic: true,
  });
}

// ---------- Slide 2: Вступление ----------
{
  const s = pres.addSlide();
  darkBg(s);
  s.addImage({ path: "art-books.png", x: 0, y: 0, w: 4.4, h: 7.5, sizing: { type: "cover", w: 4.4, h: 7.5 } });
  s.addShape("rect", { x: 0, y: 0, w: 4.4, h: 7.5, fill: { color: PANEL, transparency: 25 }, line: { type: "none" } });
  s.addText("~10\nмин", {
    x: 0.5, y: 2.6, w: 3.4, h: 2.2, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 60, color: WHITE, bold: true, align: "left", lineSpacingMultiple: 0.95,
  });
  s.addText("Продолжительность вступительной части", {
    x: 0.5, y: 4.9, w: 3.3, h: 0.8, isTextBox: true, margin: 0,
    fontFace: BODY_FONT, fontSize: 13, color: ROSE, italic: true,
  });

  kicker(s, "Часть 0", 5.1, 0.75, ROSE);
  s.addText("Вступление", {
    x: 5.05, y: 1.1, w: 7.5, h: 0.9, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 34, color: WHITE, bold: true,
  });
  s.addText("Коротко о том, что вообще будет ждать людей сегодня вечером — структура разговора, тон и то, зачем мы вообще снова говорим о Достоевском.", {
    x: 5.05, y: 2.15, w: 7.4, h: 1.2, isTextBox: true, margin: 0,
    fontFace: BODY_FONT, fontSize: 15, color: CREAM, lineSpacingMultiple: 1.25,
  });

  const items = [
    ["Зачем", "Почему Достоевский не устаревает и как читать его сегодня"],
    ["Как", "Два героя — ранний и поздний писатель — и три произведения"],
    ["О чём спорим", "Свобода, вина и право на моральный выбор"],
  ];
  let y = 3.65;
  items.forEach(([h, d]) => {
    s.addShape("ellipse", { x: 5.05, y: y + 0.05, w: 0.12, h: 0.12, fill: { color: ROSE }, line: { type: "none" } });
    s.addText(h, { x: 5.35, y: y - 0.08, w: 3, h: 0.35, isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 14, bold: true, color: ROSE });
    s.addText(d, { x: 5.35, y: y + 0.28, w: 7.1, h: 0.55, isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 12.5, color: "B8A2AA", lineSpacingMultiple: 1.15 });
    y += 1.05;
  });
  pageNum(s, 2);
}

// ---------- Slide 3: Ранний vs поздний Достоевский ----------
{
  const s = pres.addSlide();
  darkBg(s);
  kicker(s, "Часть 1", 0.8, 0.6, ROSE);
  s.addText("Ранний и поздний Достоевский", {
    x: 0.75, y: 0.98, w: 11.5, h: 0.8, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 32, color: WHITE, bold: true,
  });
  s.addText("Тезис вечера: ранний период часто недооценивают и незаслуженно забывают — а между ним и «поздним» Достоевским прямая линия развития.", {
    x: 0.8, y: 1.75, w: 11.3, h: 0.6, isTextBox: true, margin: 0,
    fontFace: BODY_FONT, fontSize: 14.5, color: CREAM, italic: true,
  });

  const colY = 2.65, colH = 4.0;
  s.addShape("roundRect", { x: 0.8, y: colY, w: 5.6, h: colH, rectRadius: 0.08, fill: { color: PANEL }, line: { type: "none" } });
  s.addShape("roundRect", { x: 6.75, y: colY, w: 5.6, h: colH, rectRadius: 0.08, fill: { color: BERRY }, line: { type: "none" } });

  s.addText("РАННИЙ", { x: 1.15, y: colY + 0.35, w: 4, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 14, bold: true, color: ROSE, charSpacing: 3 });
  s.addText("Незаслуженно забытый", { x: 1.15, y: colY + 0.75, w: 5, h: 0.5, isTextBox: true, margin: 0, fontFace: TITLE_FONT, fontSize: 22, bold: true, color: WHITE });
  s.addText(
    [
      { text: "Начало писательской карьеры — поиск голоса, эксперименты", options: { breakLine: true } },
      { text: "«Честный вор» — маленький человек, совесть, тихая трагедия", options: { breakLine: true } },
      { text: "Здесь уже есть зерно будущих тем: вина, достоинство, сострадание", options: { breakLine: false } },
    ],
    { x: 1.15, y: colY + 1.5, w: 4.9, h: 2.2, isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 13.5, color: CREAM, bullet: true, paraSpaceAfter: 12, lineSpacingMultiple: 1.2 }
  );

  s.addText("ПОЗДНИЙ", { x: 7.1, y: colY + 0.35, w: 4, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 14, bold: true, color: CREAM, charSpacing: 3 });
  s.addText("Признанный, обсуждаемый", { x: 7.1, y: colY + 0.75, w: 5, h: 0.5, isTextBox: true, margin: 0, fontFace: TITLE_FONT, fontSize: 22, bold: true, color: WHITE });
  s.addText(
    [
      { text: "«Преступление и наказание», «Записки из подполья», «Братья Карамазовы»", options: { breakLine: true } },
      { text: "Большие философские вопросы: закон, свобода, вера", options: { breakLine: true } },
      { text: "О нём говорят много — сегодня подробно останавливаться не будем", options: { breakLine: false } },
    ],
    { x: 7.1, y: colY + 1.5, w: 4.9, h: 2.2, isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 13.5, color: WHITE, bullet: true, paraSpaceAfter: 12, lineSpacingMultiple: 1.2 }
  );
  pageNum(s, 3);
}

// Reusable: section-intro slide with side artwork
function artIntroSlide(n, part, title, artPath, subtitle, rows) {
  const s = pres.addSlide();
  darkBg(s);
  s.addImage({ path: artPath, x: 8.83, y: 0, w: 4.5, h: 7.5, sizing: { type: "cover", w: 4.5, h: 7.5 } });
  s.addShape("rect", { x: 8.63, y: 0, w: 0.3, h: 7.5, fill: { color: DARK, transparency: 30 }, line: { type: "none" } });

  kicker(s, part, 0.8, 0.65, ROSE);
  s.addText(title, {
    x: 0.75, y: 1.02, w: 7.7, h: 1.0, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 32, color: WHITE, bold: true,
  });
  if (subtitle) {
    s.addText(subtitle, {
      x: 0.8, y: 1.95, w: 7.6, h: 0.7, isTextBox: true, margin: 0,
      fontFace: BODY_FONT, fontSize: 14, italic: true, color: CREAM,
    });
  }
  let y = subtitle ? 2.85 : 2.2;
  rows.forEach(([h, d]) => {
    s.addShape("roundRect", { x: 0.8, y, w: 7.6, h: 0.95, rectRadius: 0.06, fill: { color: PANEL }, line: { type: "none" } });
    s.addText(h, { x: 1.05, y: y + 0.12, w: 2.4, h: 0.72, isTextBox: true, margin: 0, valign: "middle", fontFace: BODY_FONT, fontSize: 14, bold: true, color: ROSE });
    s.addText(d, { x: 3.45, y: y + 0.12, w: 4.85, h: 0.72, isTextBox: true, margin: 0, valign: "middle", fontFace: BODY_FONT, fontSize: 12.5, color: CREAM, lineSpacingMultiple: 1.1 });
    y += 1.1;
  });
  pageNum(s, n);
  return s;
}

// ---------- Slide 4: Переход к Преступлению и наказанию ----------
artIntroSlide(
  4,
  "Переход",
  "От «Честного вора» к «Преступлению и наказанию»",
  "art-raskolnikov.png",
  "Подробно о сюжете говорить не буду — его знают почти все. Сфокусируемся на двух вопросах.",
  [
    ["Ранняя проза", "Маленький человек и его совесть"],
    ["«Честный вор»", "Достоинство на самом дне"],
    ["«Преступление и наказание»", "Совесть — против теории и закона"],
  ]
);

// Helper for "question" slides
function questionSlide(n, part, title, quote) {
  const s = pres.addSlide();
  darkBg(s);
  s.addShape("ellipse", { x: 9.8, y: -2.6, w: 6.5, h: 6.5, fill: { color: BERRY, transparency: 65 }, line: { type: "none" } });
  kicker(s, part, 0.8, 0.7, ROSE);
  s.addText("«", {
    x: 0.55, y: 1.1, w: 2, h: 2, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 120, color: BERRY, bold: true,
  });
  s.addText(title, {
    x: 1.0, y: 2.5, w: 10.8, h: 2.6, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 33, color: WHITE, bold: true, lineSpacingMultiple: 1.15,
  });
  if (quote) {
    s.addShape("line", { x: 1.05, y: 5.35, w: 0.9, h: 0, line: { color: ROSE, width: 2 } });
    s.addText(quote, {
      x: 1.05, y: 5.55, w: 10.5, h: 0.9, isTextBox: true, margin: 0,
      fontFace: BODY_FONT, fontSize: 14.5, italic: true, color: CREAM,
    });
  }
  pageNum(s, n);
  return s;
}

// ---------- Slide 5: Вопрос 1 ----------
questionSlide(
  5,
  "Вопрос 1 · Преступление и наказание",
  "Может ли человек сам определить, кому позволено переступить через моральный закон?",
  "Теория Раскольникова о «право имеющих» и «тварях дрожащих»"
);

// ---------- Slide 6: Вопрос 2 ----------
questionSlide(
  6,
  "Вопрос 2 · Преступление и наказание",
  "Опроверг ли Раскольников собственную теорию, признавшись в преступлении?",
  "Особенно интересно услышать мнения — открытый вопрос для дискуссии"
);

// ---------- Slide 7: Записки из подполья intro ----------
artIntroSlide(
  7,
  "Часть 2",
  "«Записки из подполья»",
  "art-podpolye.png",
  "Пару минут — о самом произведении, дальше сразу к вопросам.",
  [
    ["Подпольный человек", "Герой без имени — голос, полный злобы, ума и саморазрушения"],
    ["Против рацио", "Бунт против идеи, что человек всегда действует в своих интересах"],
    ["Свобода как своеволие", "Право хотеть даже то, что вредит — потому что это моё право"],
  ]
);

// ---------- Slide 8: Вопрос про рациональность ----------
questionSlide(
  8,
  "Основной вопрос · Записки из подполья",
  "Может ли человек сознательно идти против рационально выгодных для него поступков — и против собственного интереса? Почему для Достоевского это возможно?",
  "Своеволие как последний оплот личности против «хрустального дворца» разума"
);

// ---------- Slide 9: Великий инквизитор intro ----------
artIntroSlide(
  9,
  "Часть 3",
  "«Великий инквизитор»",
  "art-inkvizitor.png",
  "Короткое пояснение к притче — и снова серия вопросов. Тема — свобода, вера и счастье.",
  [
    ["Христос молчит", "Возвращается на землю, инквизитор допрашивает его в тюрьме"],
    ["Три искушения", "Хлеб, чудо и власть — то, что Христос отверг ради свободы людей"],
    ["Инквизитор", "Уверен: свобода людям не по силам, счастье важнее свободы"],
  ]
);

// ---------- Slide 10: Вопрос про свободу ----------
questionSlide(
  10,
  "Вопрос · Великий инквизитор",
  "Действительно ли человеку нужна свобода, если свобода сама становится источником страдания и ответственности?",
  "Проблема свободы, веры и счастья — можно ли выбрать хлеб вместо тяжести выбора"
);

// ---------- Slide 11: Кириллов ----------
{
  const s = pres.addSlide();
  darkBg(s);
  s.addImage({ path: "art-kirillov.png", x: 0, y: 0, w: 4.7, h: 7.5, sizing: { type: "cover", w: 4.7, h: 7.5 } });
  s.addShape("rect", { x: 4.5, y: 0, w: 0.3, h: 7.5, fill: { color: DARK, transparency: 30 }, line: { type: "none" } });

  kicker(s, "Часть 4 · Бесы", 5.05, 0.7, ROSE);
  s.addText("Кириллов", {
    x: 5.0, y: 1.1, w: 6, h: 0.7, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 30, color: WHITE, bold: true,
  });

  kicker(s, "Предельный случай", 5.05, 2.05, ROSE);
  s.addText("Что будет, если довести свободу воли до предела?", {
    x: 5.0, y: 2.5, w: 7.6, h: 1.1, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 25, color: WHITE, bold: true, lineSpacingMultiple: 1.1,
  });

  const pts = [
    "Раскольников испытывал теорию — и не выдержал её тяжести",
    "Подпольный человек защищал своеволие словом, но не действием",
    "Кириллов доводит идею до конца: своеволие как самообожествление",
  ];
  let y = 3.9;
  pts.forEach((p, i) => {
    s.addShape("roundRect", { x: 5.0, y, w: 0.5, h: 0.5, rectRadius: 0.06, fill: { color: i === 2 ? BERRY : PANEL }, line: { type: "none" } });
    s.addText(String(i + 1), { x: 5.0, y, w: 0.5, h: 0.5, isTextBox: true, margin: 0, align: "center", valign: "middle", fontFace: BODY_FONT, fontSize: 15, bold: true, color: WHITE });
    s.addText(p, { x: 5.7, y: y - 0.02, w: 6.9, h: 0.55, isTextBox: true, margin: 0, valign: "middle", fontFace: BODY_FONT, fontSize: 14, color: CREAM, lineSpacingMultiple: 1.15 });
    y += 0.85;
  });

  s.addText("Финальный вопрос вечера: где проходит граница между свободой и саморазрушением?", {
    x: 5.0, y: 6.45, w: 7.5, h: 0.9, isTextBox: true, margin: 0,
    fontFace: BODY_FONT, fontSize: 14.5, italic: true, color: ROSE, bold: true, lineSpacingMultiple: 1.25,
  });
  pageNum(s, 11);
}

// ---------- Slide 12: Итог — маршрут вечера ----------
{
  const s = pres.addSlide();
  darkBg(s);
  kicker(s, "Маршрут вечера", 0.8, 0.65, ROSE);
  s.addText("Один вечер — четыре героя, один вопрос", {
    x: 0.75, y: 1.0, w: 11.5, h: 0.8, isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 30, color: WHITE, bold: true,
  });

  const stops = [
    ["Вступление", "10 мин", "Что нас ждёт"],
    ["Раскольников", "П. и Н.", "Право на закон"],
    ["Подпольный человек", "Записки", "Против рацио"],
    ["Инквизитор", "Легенда", "Свобода и счастье"],
    ["Кириллов", "Бесы", "Своеволие до предела"],
  ];
  const n = stops.length, startX = 0.8, endX = 12.55, y0 = 3.5;
  const usableW = endX - startX;
  s.addShape("line", { x: startX, y: y0, w: usableW, h: 0, line: { color: ROSE, width: 2 } });
  stops.forEach((st, i) => {
    const cx = startX + (usableW / (n - 1)) * i;
    s.addShape("ellipse", { x: cx - 0.11, y: y0 - 0.11, w: 0.22, h: 0.22, fill: { color: i === 0 ? ROSE : BERRY }, line: { color: CREAM, width: 1.5 } });
    const boxW = 2.3;
    s.addText(st[1].toUpperCase(), { x: cx - boxW / 2, y: y0 - 1.05, w: boxW, h: 0.3, align: "center", isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 10.5, color: ROSE, bold: true, charSpacing: 1 });
    s.addText(st[0], { x: cx - boxW / 2, y: y0 - 0.72, w: boxW, h: 0.5, align: "center", isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 14, color: WHITE, bold: true });
    s.addText(st[2], { x: cx - boxW / 2, y: y0 + 0.3, w: boxW, h: 0.6, align: "center", isTextBox: true, margin: 0, fontFace: BODY_FONT, fontSize: 12, color: CREAM, italic: true, lineSpacingMultiple: 1.15 });
  });

  s.addText("Сквозная тема: свобода всегда стоит цену — вопрос в том, кто и как готов её платить.", {
    x: 1.5, y: 6.0, w: 10.3, h: 0.7, align: "center", isTextBox: true, margin: 0,
    fontFace: TITLE_FONT, fontSize: 18, italic: true, color: CREAM,
  });
  pageNum(s, 12);
}

pres.writeFile({ fileName: "Dostoevsky_Lecture.pptx" }).then(() => {
  console.log("done");
});
