// Survival LLM's interface in Dutch (Nederlands), for i18n.js. See i18n.js for how a language pack works.
// Keys are the English the app writes (app.js, index.html, app/server.py); values are the Dutch. The AI's own Dutch
// instructions are in core.py (LANGUAGE_PROMPTS).
window.i18n.register("nl", ({ tr, NUM }) => {
  // Library pack names (packs on the download site are named in English).
  const NAMES = { Essentials: "Basis", Everything: "Alles", Library: "Bibliotheek" };
  const name = (s) => NAMES[s] || s;
  const bin = (s) => ({ Trash: "prullenbak", "Recycle Bin": "Prullenbak" }[s] || s);

  // "about 3 minutes", "About 1 hour 20 minutes" (app.js timeText)
  function time(s) {
    const cap = /^A/.test(s);
    let out = s.replace(/^[Aa]bout /, "ongeveer ")
      .replace(/^ongeveer a minute$/, "ongeveer een minuut")
      .replace(/(\d+) hours? (\d+) minutes/, "$1 uur en $2 minuten")
      .replace(/(\d+) hours?/, "$1 uur")
      .replace(/(\d+) minutes/, "$1 minuten");
    return cap ? out.charAt(0).toUpperCase() + out.slice(1) : out;
  }
  const T = "((?:[Aa]bout) (?:a minute|\\d+ hours?(?: \\d+ minutes)?|\\d+ minutes))";
  const N = NUM;  // a number as toLocaleString writes it

  // " Graphics card: AMD Radeon RX 7800 XT with 16 GB of memory, which the AI uses." (app.js gpuText)
  function gpuNL(s) {
    if (!s) return "";
    if (s.trim() === "No graphics card found, so models run from main memory.")
      return " Geen videokaart gevonden, dus modellen draaien uit het werkgeheugen.";
    const m = s.match(/^ ?Graphics card: (.+) with (\d+) GB of memory, (which the AI uses|which the AI engine can't use, so models run from main memory)\.$/);
    if (!m) return null;
    return ` Videokaart: ${m[1] === "Unknown" ? "onbekend" : m[1]} met ${m[2]} GB geheugen, `
      + (m[3] === "which the AI uses" ? "die de AI gebruikt." : "die de AI-motor niet kan gebruiken, dus modellen draaien uit het werkgeheugen.");
  }

  const EXACT = {
    // ---------- top bar and welcome ----------
    "Starting…": "Bezig met starten…",
    "Choose which AI model answers": "Kies welk AI-model antwoordt",
    "none yet": "nog geen",
    "Search library": "Zoek in bibliotheek",
    "Your files": "Je bestanden",
    "Add your own documents for the AI to search": "Voeg je eigen documenten toe zodat de AI erin zoekt",
    "Memory": "Geheugen",
    "See and edit what the AI remembers about you": "Bekijk en bewerk wat de AI over je onthoudt",
    "Instructions": "Instructies",
    "See and edit the instructions the AI follows": "Bekijk en bewerk de instructies die de AI volgt",
    "New chat": "Nieuw gesprek",
    "Quit": "Afsluiten",
    "Stop Survival LLM": "Survival LLM stoppen",
    "Chat": "Gesprek",
    "See what's new": "Bekijk wat er nieuw is",
    "Not now": "Niet nu",
    "Close": "Sluiten",
    "✓ Setup is done. Survival LLM now works without internet.": "✓ De installatie is klaar. Survival LLM werkt nu zonder internet.",
    "Setup is done. Survival LLM now works without internet.": "De installatie is klaar. Survival LLM werkt nu zonder internet.",
    "Ask anything. No internet needed.": "Vraag wat je wilt. Geen internet nodig.",
    "A local AI looks things up in an offline library of medical, emergency, how-to and encyclopedia articles, then tells you where each answer came from. Click a source to read it yourself. Add your own documents with":
      "Een AI op je eigen computer zoekt dingen op in een offline bibliotheek met artikelen over medische zaken, noodsituaties, praktische klussen en algemene kennis, en vertelt je waar elk antwoord vandaan komt. Klik op een bron om die zelf te lezen. Voeg je eigen documenten toe met",
    "at the top, and it searches those too. It remembers what you tell it about yourself between chats; see and edit that in":
      "bovenaan, en dan zoekt hij daar ook in. Hij onthoudt tussen gesprekken door wat je over jezelf vertelt; dat bekijk en bewerk je in",
    "The power is out. How long is the food in my fridge safe?": "De stroom is uitgevallen. Hoe lang blijft het eten in mijn koelkast goed?",
    "Where can I safely run a generator?": "Waar kan ik veilig een aggregaat laten draaien?",
    "How do I make tap water safe to drink?": "Hoe maak ik kraanwater veilig om te drinken?",
    "Someone burned their hand on the stove. What do I do?": "Iemand heeft zijn hand aan het fornuis verbrand. Wat moet ik doen?",
    // ---------- question box ----------
    "Ask a question…": "Stel een vraag…",
    "Your question": "Je vraag",
    "Reasoning": "Redeneren",
    "How much the AI may think before it answers. At the limit its thinking is cut off and it answers from what it has. More thinking is slower, and often more careful. A token is about three quarters of a word. Qwen thinks a little even when this is Off.":
      "Hoeveel de AI mag redeneren voordat hij antwoordt. Bij de grens wordt het redeneren afgebroken en antwoordt hij met wat hij heeft. Meer redeneren is trager, en vaak zorgvuldiger. Een token is ongeveer driekwart woord. Qwen denkt ook een beetje na als dit op Uit staat.",
    "Off": "Uit",
    "Short (1,000 tokens)": "Kort (1.000 tokens)",
    "Medium (4,000 tokens)": "Middel (4.000 tokens)",
    "Long (16,000 tokens)": "Lang (16.000 tokens)",
    "No limit": "Geen grens",
    "Length limit": "Lengtegrens",
    "Normal stops an answer after about 6,000 words, Long after about 25,000. None never stops it on its own; use Stop if it gets stuck.":
      "Normaal stopt een antwoord na ongeveer 6.000 woorden, Lang na ongeveer 25.000. Geen stopt nooit vanzelf; gebruik Stop als hij vastloopt.",
    "Normal": "Normaal",
    "Long": "Lang",
    "None": "Geen",
    "Send": "Verstuur",
    "Send question": "Vraag versturen",
    "Stop": "Stop",
    "Stop the answer": "Antwoord stoppen",
    "AI can make mistakes. Check the sources.": "AI kan fouten maken. Controleer de bronnen.",
    "Check for updates": "Zoek naar updates",
    "Update available": "Update beschikbaar",
    "Language": "Taal",
    "With no reasoning limit, a model can get stuck reasoning in circles and keep going until you press Stop.":
      "Zonder grens aan het redeneren kan een model in rondjes blijven denken tot je op Stop drukt.",
    "With no length limit, a model stuck repeating itself keeps going until you press Stop.":
      "Zonder lengtegrens gaat een model dat zichzelf blijft herhalen door tot je op Stop drukt.",
    "With no reasoning limit, a model can get stuck reasoning in circles and keep going until you press Stop. With no length limit, a model stuck repeating itself keeps going until you press Stop.":
      "Zonder grens aan het redeneren kan een model in rondjes blijven denken tot je op Stop drukt. Zonder lengtegrens gaat een model dat zichzelf blijft herhalen door tot je op Stop drukt.",
    // ---------- reader ----------
    "Search the library yourself…": "Zoek zelf in de bibliotheek…",
    "Search the library": "Zoek in de bibliotheek",
    "Library and sources": "Bibliotheek en bronnen",
    "Switch or move the library": "Wissel of verplaats de bibliotheek",
    "Opening…": "Bezig met openen…",
    "Couldn't open that source.": "Die bron kon niet worden geopend.",
    "Searching…": "Bezig met zoeken…",
    "Official": "Officieel",
    "Published by a government or health agency. They do not endorse this app.":
      "Gepubliceerd door een overheid of gezondheidsinstantie. Zij staan niet achter deze app.",
    "The answer used this part": "Het antwoord gebruikte dit deel",
    "The answer pointed here": "Het antwoord verwees hierheen",
    "This matched the search": "Dit kwam overeen met de zoekopdracht",
    "This matched your search": "Dit kwam overeen met je zoekopdracht",
    "License": "Licentie",
    // ---------- dialogs ----------
    "AI models": "AI-modellen",
    "AI instructions": "Instructies voor de AI",
    "Survival LLM gives the AI these instructions at the start of every conversation. Change them to change how it answers. Your version applies to every model, from your next question; Reset brings back the original. After these, the app adds today's date, the answer language (when it isn't English), the names of your files and the AI's notes about you (see Memory).":
      "Survival LLM geeft de AI deze instructies aan het begin van elk gesprek. Pas ze aan om te veranderen hoe hij antwoordt. Jouw versie geldt voor elk model, vanaf je volgende vraag; Herstel brengt het origineel terug. Daarna voegt de app de datum van vandaag, de antwoordtaal (als die niet Engels is), de namen van je bestanden en de notities van de AI over jou toe (zie Geheugen).",
    "Reset to default": "Herstel origineel",
    "Save": "Opslaan",
    "Add your own documents and the AI searches them along with the library: manuals for your generator or medical devices, prescriptions, your family's emergency plan, notes. PDF, Word, EPUB, web pages and text files. They stay on this computer.":
      "Voeg je eigen documenten toe en de AI doorzoekt ze samen met de bibliotheek: handleidingen van je aggregaat of medische apparaten, recepten, het noodplan van je gezin, notities. PDF, Word, EPUB, webpagina's en tekstbestanden. Ze blijven op deze computer.",
    "Drop files here, or": "Sleep bestanden hierheen, of",
    "Choose files": "Kies bestanden",
    "Replace it": "Vervang het",
    "Keep both": "Bewaar allebei",
    "Don't add it": "Niet toevoegen",
    "Open the folder": "Open de map",
    "Use another folder…": "Gebruik een andere map…",
    "What the AI remembers about you between chats: who's in your household, health and medicines, your equipment, what your files are. It reads these at the start of every chat. Edit them here, one note per line. They stay on this computer.":
      "Wat de AI tussen gesprekken door over je onthoudt: wie er in je huishouden zijn, gezondheid en medicijnen, je uitrusting, wat je bestanden zijn. Hij leest dit aan het begin van elk gesprek. Bewerk het hier, één notitie per regel. Het blijft op deze computer. (De AI schrijft zijn notities in het Engels.)",
    "Let the AI add and change notes": "Laat de AI notities toevoegen en wijzigen",
    "Memory notes, one per line": "Geheugennotities, één per regel",
    "Nothing yet. Notes appear here as the AI learns about you, or write your own, one per line. For example: My son Leo (9) has type 1 diabetes.":
      "Nog niets. Notities verschijnen hier als de AI meer over je leert, of schrijf ze zelf, één per regel. Bijvoorbeeld: Mijn zoon Leo (9) heeft diabetes type 1.",
    "Delete all": "Alles wissen",
    "Library": "Bibliotheek",
    "Updates": "Updates",
    "Drop to add to Your files": "Loslaten om aan Je bestanden toe te voegen",
    "Survival LLM was restarted.": "Survival LLM is opnieuw gestart.",
    "Reload this page": "Laad deze pagina opnieuw",
    // ---------- status line ----------
    "Restarting into the new version…": "Bezig met opnieuw starten in de nieuwe versie…",
    "Survival LLM has stopped. Open the app again.": "Survival LLM is gestopt. Open de app opnieuw.",
    "Starting the AI engine…": "De AI-motor wordt gestart…",
    "The AI engine (Ollama) isn't running ·": "De AI-motor (Ollama) draait niet ·",
    "Start it": "Start hem",
    "Setup not finished: the AI engine is needed": "Installatie niet klaar: de AI-motor is nodig",
    "Setup not finished: needs an AI model": "Installatie niet klaar: er is een AI-model nodig",
    "Setup not finished: needs the library": "Installatie niet klaar: de bibliotheek is nodig",
    "Setup not finished: needs an AI model and the library": "Installatie niet klaar: een AI-model en de bibliotheek zijn nodig",
    "Not set up yet": "Nog niet geïnstalleerd",
    "Ready to use without internet ·": "Klaar voor gebruik zonder internet ·",
    "Switch libraries or move the library": "Wissel van bibliotheek of verplaats hem",
    "Answering with": "Antwoordt met",
    "Change model": "Ander model",
    ".": ".",
    // ---------- models ----------
    "Starts a new chat: click again": "Begint een nieuw gesprek: klik nogmaals",
    "Recommended for this computer": "Aanbevolen voor deze computer",
    "In use": "In gebruik",
    "Use this": "Gebruik dit",
    "Downloaded": "Gedownload",
    "Try again": "Probeer opnieuw",
    "Start the AI engine first": "Start eerst de AI-motor",
    "Too big for this computer": "Te groot voor deze computer",
    "Other models on this computer": "Andere modellen op deze computer",
    "Another copy of a model listed above.": "Een andere kopie van een model hierboven.",
    "Not tested with Survival LLM; answers may be worse.": "Niet getest met Survival LLM; antwoorden kunnen slechter zijn.",
    // model descriptions (app/server.py CATALOG)
    "The smartest option: knows the most and is the least likely to make things up. Quick on Apple Silicon.":
      "De slimste keuze: weet het meest en verzint het minst. Snel op Apple Silicon.",
    "The smartest option: knows the most and is the least likely to make things up. Needs a powerful PC.":
      "De slimste keuze: weet het meest en verzint het minst. Heeft een krachtige computer nodig.",
    "Careful and thorough: looks things up for every question. A great fit for 32-64 GB Macs.":
      "Zorgvuldig en grondig: zoekt bij elke vraag dingen op. Past heel goed bij Macs met 32-64 GB.",
    "Careful and thorough, but slow unless your PC has a graphics card with 24 GB of memory.":
      "Zorgvuldig en grondig, maar traag tenzij je computer een videokaart met 24 GB geheugen heeft.",
    "The fastest: answers in a few seconds and saves battery. Sometimes misses details.":
      "De snelste: antwoordt in een paar seconden en spaart de accu. Mist soms details.",
    "The best choice for most PCs: accurate and careful. Expect up to a minute per answer on a typical PC.":
      "De beste keuze voor de meeste computers: nauwkeurig en zorgvuldig. Reken op maximaal een minuut per antwoord op een gewone computer.",
    "For 16 GB computers. Always looks things up and shows its sources, but makes more mistakes than the bigger models, so check the source.":
      "Voor computers met 16 GB. Zoekt altijd dingen op en laat zijn bronnen zien, maar maakt meer fouten dan de grotere modellen, dus controleer de bron.",
    "Small and very fast, for 16 GB computers. Often answers from memory instead of the library, so check what it says.":
      "Klein en heel snel, voor computers met 16 GB. Antwoordt vaak uit zijn geheugen in plaats van uit de bibliotheek, dus controleer wat hij zegt.",
    // ---------- library packs (docs/library-packs.json) ----------
    "Medical, emergency, survival, how-to and repair": "Medisch, noodsituaties, overleven, praktische klussen en reparatie",
    "Essentials plus about 930,000 of Wikipedia's most-read articles and iFixit":
      "Basis plus ongeveer 930.000 van de meestgelezen Wikipedia-artikelen en iFixit",
    "It drops about 2,700 repeated pages, so searches show more different articles.":
      "Er zijn ongeveer 2.700 dubbele pagina's uit, zodat zoekopdrachten meer verschillende artikelen laten zien.",
    // ---------- library missing, setup ----------
    "The library isn't where it was:": "De bibliotheek staat niet meer waar hij stond:",
    ". If it's on a drive, plug the drive in.": ". Staat hij op een externe schijf, sluit die dan aan.",
    "Library window": "Bibliotheekvenster",
    "No library yet, so answers come from the AI's memory alone, with no sources to check.":
      "Nog geen bibliotheek, dus antwoorden komen alleen uit het geheugen van de AI, zonder bronnen om te controleren.",
    "Get the library": "Download de bibliotheek",
    "Unpacking… (a few minutes)": "Bezig met uitpakken… (een paar minuten)",
    "Leave Survival LLM open until it finishes. If it gets interrupted, start it again and it picks up where it left off.":
      "Laat Survival LLM open tot het klaar is. Wordt het onderbroken, start het dan opnieuw en het gaat verder waar het was.",
    "The list of libraries isn't available right now (the download site answered, but without it). It checks again every minute.":
      "De lijst met bibliotheken is nu niet beschikbaar (de downloadsite antwoordde, maar zonder lijst). Er wordt elke minuut opnieuw gekeken.",
    "Connect to the internet to download the library; this page notices on its own when you're online. If you have a library folder already (from a USB stick, say), choose it with Keep it somewhere else below.":
      "Maak verbinding met internet om de bibliotheek te downloaden; deze pagina merkt vanzelf wanneer je online bent. Heb je al een bibliotheekmap (van een USB-stick bijvoorbeeld), kies die dan hieronder met Bewaar hem ergens anders.",
    "Getting the list of libraries…": "Bezig met ophalen van de lijst met bibliotheken…",
    "Getting the AI engine ready… (a few seconds)": "De AI-motor wordt klaargemaakt… (een paar seconden)",
    "The AI engine didn't start.": "De AI-motor is niet gestart.",
    "Start it again": "Start hem opnieuw",
    "Already on this computer": "Staat al op deze computer",
    " (seconds in this preview: it's on this Mac)": " (seconden in deze proefversie: hij staat al op deze Mac)",
    "Best for this computer": "Beste voor deze computer",
    "Not tested yet": "Nog niet getest",
    "Not tested with Survival LLM yet. Quick for its size: only about 3.6 billion of its 21 billion parameters work on each word. Strongest in English.":
      "Nog niet getest met Survival LLM. Snel voor zijn grootte: maar ongeveer 3,6 miljard van zijn 21 miljard parameters werken aan elk woord. Het sterkst in het Engels.",
    "Not tested with Survival LLM yet. As quick as Nemotron Lightning (about 3 billion parameters work on each word), and Qwen models are good at languages other than English, Dutch included.":
      "Nog niet getest met Survival LLM. Even snel als Nemotron Lightning (ongeveer 3 miljard parameters werken aan elk woord), en Qwen-modellen zijn goed in andere talen dan Engels, ook in het Nederlands.",
    "Survival LLM uses the free Ollama app to run the AI on this computer. Install it while you have internet:":
      "Survival LLM gebruikt de gratis app Ollama om de AI op deze computer te draaien. Installeer die zolang je internet hebt:",
    ". Setup carries on by itself once Ollama is running.": ". De installatie gaat vanzelf verder zodra Ollama draait.",
    "Getting ready…": "Bezig met klaarmaken…",
    "Download": "Downloaden",
    "on typical home internet (50 Mb/s). It keeps going if the internet drops or the computer sleeps.":
      "met gewoon thuisinternet (50 Mb/s). Het gaat door als het internet wegvalt of de computer slaapt.",
    "It will be kept in": "Hij wordt bewaard in",
    "Keep it somewhere else": "Bewaar hem ergens anders",
    "Set up Survival LLM": "Survival LLM installeren",
    "Survival LLM is an AI that runs on this computer. It answers from an offline library of medical, emergency and how-to articles, and shows you where each answer came from. Download both once, while you have internet; after that it works with none. If you quit halfway, it picks up where it left off the next time you open it.":
      "Survival LLM is een AI die op deze computer draait. Hij antwoordt uit een offline bibliotheek met artikelen over medische zaken, noodsituaties en praktische klussen, en laat zien waar elk antwoord vandaan komt. Download beide één keer, zolang je internet hebt; daarna werkt het zonder. Stop je halverwege, dan gaat het de volgende keer verder waar het was.",
    "The library": "De bibliotheek",
    "What the AI looks things up in. You can read it yourself, too.": "Waarin de AI dingen opzoekt. Je kunt hem ook zelf lezen.",
    "The AI": "De AI",
    "Runs on this computer and writes the answers. Bigger ones know more and make fewer mistakes.":
      "Draait op deze computer en schrijft de antwoorden. Grotere weten meer en maken minder fouten.",
    "AI engine": "AI-motor",
    "Ready.": "Klaar.",
    "Search it now": "Doorzoek hem nu",
    "The download stopped.": "De download is gestopt.",
    "Try now": "Probeer nu",
    "Install the free Ollama app to run it:": "Installeer de gratis app Ollama om hem te draaien:",
    "Setup carries on by itself once Ollama is running.": "De installatie gaat vanzelf verder zodra Ollama draait.",
    "Next": "Hierna",
    "(on this Mac already, so in this preview it takes seconds)": "(staat al op deze Mac, dus in deze proefversie duurt het seconden)",
    "Download speed in megabits a second, the unit internet plans use":
      "Downloadsnelheid in megabit per seconde, de eenheid van internetabonnementen",
    "The library is ready, so you can already search it yourself while the AI downloads.":
      "De bibliotheek is klaar, dus je kunt er al zelf in zoeken terwijl de AI downloadt.",
    "Setting up Survival LLM": "Survival LLM wordt geïnstalleerd",
    "Leave Survival LLM open, with the computer plugged in if you can. If the internet drops or the computer sleeps, it carries on by itself; if you quit, it picks up where it left off the next time you open it.":
      "Laat Survival LLM open, met de computer aan de stroom als dat kan. Valt het internet weg of slaapt de computer, dan gaat het vanzelf verder; stop je, dan gaat het de volgende keer verder waar het was.",
    "Click again to stop the download and choose again": "Klik nogmaals om de download te stoppen en opnieuw te kiezen",
    "Change what to download": "Kies opnieuw wat je downloadt",
    "The library isn't downloaded yet, so answers come from the AI's memory alone, with no sources to check.":
      "De bibliotheek is nog niet gedownload, dus antwoorden komen alleen uit het geheugen van de AI, zonder bronnen om te controleren.",
    "Couldn't start the download.": "De download kon niet starten.",
    "Downloading. This page shows how far along it is.": "Bezig met downloaden. Deze pagina laat zien hoe ver het is.",
    // ---------- Library window ----------
    "Download, update or move the library and its sources": "Download, werk bij of verplaats de bibliotheek en zijn bronnen",
    "A fresh copy, for a damaged library or to start over. Extra sources you added come back by themselves.":
      "Een nieuwe kopie, voor een beschadigde bibliotheek of om opnieuw te beginnen. Extra bronnen die je toevoegde komen vanzelf terug.",
    "Extra sources": "Extra bronnen",
    "Downloaded from their own websites and added to your library. They aren't in the library downloads.":
      "Gedownload van hun eigen websites en toegevoegd aan je bibliotheek. Ze zitten niet in de bibliotheekdownloads.",
    "In Dutch: self-sufficiency, food storage, water, energy and the local economy. About 40 articles, under 1 MB. For your own use: the site states no license, so it is never in the library downloads.":
      "In het Nederlands: zelfvoorziening, voedsel bewaren, water, energie en de lokale economie. Ongeveer 40 artikelen, minder dan 1 MB. Voor eigen gebruik: de site vermeldt geen licentie, dus hij zit nooit in de bibliotheekdownloads.",
    "Update": "Bijwerken",
    "Click again to remove it": "Klik nogmaals om hem te verwijderen",
    "Couldn't start that.": "Dat kon niet starten.",
    "Install a library first, then add extra sources to it.": "Installeer eerst een bibliotheek en voeg er dan extra bronnen aan toe.",
    "The website is busy (too many downloads from this internet connection). Try again in a few minutes.":
      "De website is druk (te veel downloads vanaf deze internetverbinding). Probeer het over een paar minuten opnieuw.",
    "Couldn't reach the website. Check the internet connection.": "De website was niet bereikbaar. Controleer de internetverbinding.",
    "Your library": "Je bibliotheek",
    "No library yet": "Nog geen bibliotheek",
    "Pick one below. Until then the AI answers from its memory alone, with no sources to check.":
      "Kies er hieronder een. Tot dan antwoordt de AI alleen uit zijn geheugen, zonder bronnen om te controleren.",
    "Kept in": "Bewaard in",
    "Moving the library to the new folder…": "Bezig met verplaatsen van de bibliotheek naar de nieuwe map…",
    "Library move": "Bibliotheek verplaatsen",
    "Show the folder": "Toon de map",
    "Move it…": "Verplaats hem…",
    "Keep it somewhere else…": "Bewaar hem ergens anders…",
    "Move it to another folder or an external drive. If that folder already holds a library, Survival LLM uses that one instead.":
      "Verplaats hem naar een andere map of een externe schijf. Staat er in die map al een bibliotheek, dan gebruikt Survival LLM die.",
    "Pick where the library goes before you download it, an external drive for instance.":
      "Kies waar de bibliotheek komt voordat je hem downloadt, bijvoorbeeld een externe schijf.",
    "Click again to download it": "Klik nogmaals om hem te downloaden",
    "Connect to the internet to see the libraries you can download.": "Maak verbinding met internet om te zien welke bibliotheken je kunt downloaden.",
    "The list of libraries isn't available right now. It checks again every minute.":
      "De lijst met bibliotheken is nu niet beschikbaar. Er wordt elke minuut opnieuw gekeken.",
    "Which folder should the library go in?": "In welke map moet de bibliotheek komen?",
    "Couldn't move the library.": "De bibliotheek kon niet worden verplaatst.",
    "That folder already had a library, so Survival LLM uses it now.": "In die map stond al een bibliotheek, dus Survival LLM gebruikt die nu.",
    "The library is already there.": "De bibliotheek staat daar al.",
    // ---------- chat ----------
    "Download an AI first (in the setup above). Your question will wait here.":
      "Download eerst een AI (in de installatie hierboven). Je vraag blijft hier staan.",
    "Working on it…": "Bezig…",
    "Show reasoning": "Redenatie tonen",
    "Hide reasoning": "Redenatie verbergen",
    "No reasoning yet.": "Nog niet nagedacht.",
    "No reasoning to show for this answer.": "Er is voor dit antwoord geen redenatie om te laten zien.",
    "Before it answers, the AI thinks by writing notes to itself, and looks things up in between. In its notes, “the user” means you. They can include ideas it dropped along the way, so go by the answer.":
      "Voordat hij antwoordt, denkt de AI na door notities voor zichzelf te schrijven, en zoekt hij tussendoor dingen op. In zijn notities betekent “the user” jou. Er kunnen ideeën in staan die hij onderweg heeft laten vallen, dus ga uit van het antwoord. (De AI denkt vaak in het Engels.)",
    "Thought": "Gedachte",
    "Searched": "Gezocht",
    "Read": "Gelezen",
    "Opened": "Geopend",
    "Limit": "Grens",
    "Searched the library": "Bibliotheek doorzocht",
    "Opened for you": "Voor je geopend",
    "Loading the AI into memory. The first answer can take a minute, and the fans may spin up; that's normal.":
      "De AI wordt in het geheugen geladen. Het eerste antwoord kan een minuut duren, en de ventilatoren kunnen gaan draaien; dat is normaal.",
    "It answered from memory, so it was asked to search the library, as you asked.":
      "Hij antwoordde uit zijn geheugen, dus is hem gevraagd de bibliotheek te doorzoeken, zoals jij vroeg.",
    "It hadn't written an answer, so it was given the best articles it found and asked again.":
      "Hij had geen antwoord geschreven, dus kreeg hij de beste artikelen die hij vond en is het hem opnieuw gevraagd.",
    "Couldn't update memory this time.": "Het geheugen kon deze keer niet worden bijgewerkt.",
    "Memory didn't change. You can edit it yourself:": "Het geheugen is niet veranderd. Je kunt het zelf bewerken:",
    "Keep going": "Ga verder",
    "Stopped updating memory. Anything it already saved is in Memory.":
      "Gestopt met het bijwerken van het geheugen. Wat al was opgeslagen staat in Geheugen.",
    "Stopped.": "Gestopt.",
    "Details": "Details",
    "Sources it read · click to open": "Geraadpleegde artikelen · klik om te openen",
    "It searched, but didn't open any of these · click to read them": "Gevonden maar niet geraadpleegde artikelen · klik om ze te lezen",
    "This answer came from what the AI already knows, not the library, so there's no source to check. Ask “look that up” to get one.":
      "Dit antwoord komt uit wat de AI al weet, niet uit de bibliotheek, dus er is geen bron om te controleren. Vraag “zoek het op” om er een te krijgen.",
    "No library installed yet, so this answer came from what the AI already knows, with no source to check.":
      "Er is nog geen bibliotheek geïnstalleerd, dus dit antwoord komt uit wat de AI al weet, zonder bron om te controleren.",
    "Updating memory…": "Geheugen wordt bijgewerkt…",
    "See memory": "Bekijk geheugen",
    "Changed its memory": "Heeft zijn geheugen aangepast",
    "Undo": "Ongedaan maken",
    // ---------- your files ----------
    "Survival LLM can't read this kind of file. It reads PDF, Word, EPUB, web pages and text files.":
      "Survival LLM kan dit soort bestand niet lezen. Het leest PDF, Word, EPUB, webpagina's en tekstbestanden.",
    "Ready: the AI searches it": "Klaar: de AI doorzoekt het",
    "The AI can't search this one": "De AI kan dit bestand niet doorzoeken",
    "Remove": "Verwijderen",
    "No files yet.": "Nog geen bestanden.",
    "couldn't add it.": "kon niet worden toegevoegd.",
    "couldn't add it. Is Survival LLM still running?": "kon niet worden toegevoegd. Draait Survival LLM nog?",
    "Which folder are your files in?": "In welke map staan je bestanden?",
    "Survival LLM now searches the files in that folder. The files in the old folder stay where they were.":
      "Survival LLM doorzoekt nu de bestanden in die map. De bestanden in de oude map blijven waar ze waren.",
    "Couldn't use that folder.": "Die map kan niet worden gebruikt.",
    "Couldn't read this file. It may be damaged, or saved in a way Survival LLM doesn't understand.":
      "Dit bestand kon niet worden gelezen. Het is misschien beschadigd, of opgeslagen op een manier die Survival LLM niet begrijpt.",
    "There's no text in this file.": "Er staat geen tekst in dit bestand.",
    // ---------- updates ----------
    "Checking for updates…": "Bezig met zoeken naar updates…",
    "Couldn't check for updates. Is Survival LLM still running?": "Kon niet zoeken naar updates. Draait Survival LLM nog?",
    "Update download": "Update downloaden",
    "Installed. Survival LLM is restarting into the new version…": "Geïnstalleerd. Survival LLM start opnieuw in de nieuwe versie…",
    "Get the new version from the website": "Haal de nieuwe versie van de website",
    "Update now": "Nu bijwerken",
    "Survival LLM downloads the new version, closes, and opens again a few seconds later. Your AI models, library, files and settings stay as they are.":
      "Survival LLM downloadt de nieuwe versie, sluit af, en opent een paar seconden later weer. Je AI-modellen, bibliotheek, bestanden en instellingen blijven zoals ze zijn.",
    "A newer library is available": "Er is een nieuwere bibliotheek",
    "Downloading the new library": "Bezig met downloaden van de nieuwe bibliotheek",
    "Library update": "Bibliotheek bijwerken",
    "Your library is up to date.": "Je bibliotheek is bijgewerkt.",
    "Your current library keeps working until the new one is ready, and your own files stay.":
      "Je huidige bibliotheek blijft werken tot de nieuwe klaar is, en je eigen bestanden blijven staan.",
    "To switch between Essentials and Everything, or move the library:": "Om te wisselen tussen Basis en Alles, of de bibliotheek te verplaatsen:",
    "The update couldn't start. Try again.": "De update kon niet starten. Probeer het opnieuw.",
    "This is a dev copy of Survival LLM (started with bin/dev), so it doesn't update itself.":
      "Dit is een ontwikkelkopie van Survival LLM (gestart met bin/dev), dus die werkt zichzelf niet bij.",
    "This copy of Survival LLM runs from its source code, so it can't update itself. Update it with git pull.":
      "Deze kopie van Survival LLM draait vanuit de broncode, dus kan zichzelf niet bijwerken. Werk hem bij met git pull.",
    "Survival LLM can't replace itself in the folder it's in. Download the new version from the website.":
      "Survival LLM kan zichzelf niet vervangen in de map waar het staat. Download de nieuwe versie van de website.",
    // ---------- memory ----------
    "These are your unsaved changes. Save keeps them, along with anything the AI changed since.":
      "Dit zijn je niet-opgeslagen wijzigingen. Opslaan bewaart ze, samen met wat de AI sindsdien veranderde.",
    "Couldn't load the memory.": "Het geheugen kon niet worden geladen.",
    "The AI just changed its notes. Save keeps your edits and its changes.":
      "De AI heeft net zijn notities aangepast. Opslaan bewaart jouw wijzigingen en die van hem.",
    "Saving…": "Bezig met opslaan…",
    "Couldn't save.": "Opslaan lukte niet.",
    "Not saved: Survival LLM restarted. Copy your edits, then reload the page.":
      "Niet opgeslagen: Survival LLM is opnieuw gestart. Kopieer je wijzigingen en laad de pagina opnieuw.",
    "Couldn't save. Is Survival LLM still running?": "Opslaan lukte niet. Draait Survival LLM nog?",
    "Saved. Used from your next question.": "Opgeslagen. Wordt gebruikt vanaf je volgende vraag.",
    "Click again to delete every note": "Klik nogmaals om alle notities te wissen",
    "Deleted all notes.": "Alle notities gewist.",
    "Couldn't change that.": "Dat kon niet worden gewijzigd.",
    "The AI can add and change notes again.": "De AI kan weer notities toevoegen en wijzigen.",
    "The AI won't add or change notes now. It still reads the ones here.":
      "De AI voegt nu geen notities toe en wijzigt ze niet. Hij leest de notities hier nog wel.",
    "Couldn't change that. Is Survival LLM still running?": "Dat kon niet worden gewijzigd. Draait Survival LLM nog?",
    // ---------- instructions, quit ----------
    "Using your edited instructions.": "Je eigen aangepaste instructies worden gebruikt.",
    "Using the original instructions.": "De originele instructies worden gebruikt.",
    "Couldn't load the instructions.": "De instructies konden niet worden geladen.",
    "Back to the original instructions.": "Terug naar de originele instructies.",
    "Click again to quit": "Klik nogmaals om af te sluiten",
    "Survival LLM has stopped.": "Survival LLM is gestopt.",
    "You can close this window. Open Survival LLM again to start it.": "Je kunt dit venster sluiten. Open Survival LLM opnieuw om het te starten.",
    // ---------- messages from the server (app/server.py) ----------
    "Couldn't save: the disk is full. Free some space and try again.": "Opslaan lukte niet: de schijf is vol. Maak wat ruimte vrij en probeer het opnieuw.",
    "This model needs a newer AI engine than the one built into this version of Survival LLM. Check for updates (at the bottom of the window); until then, pick another model under Model.":
      "Dit model heeft een nieuwere AI-motor nodig dan die in deze versie van Survival LLM. Zoek naar updates (onderaan het venster); kies tot dan een ander model onder Model.",
    "This model needs a newer AI engine than the one Survival LLM installed. Pick another model under Model.":
      "Dit model heeft een nieuwere AI-motor nodig dan die Survival LLM installeerde. Kies een ander model onder Model.",
    "This model isn't installed. Open Model at the top to download it or pick another.":
      "Dit model is niet geïnstalleerd. Open Model bovenaan om het te downloaden of kies een ander.",
    "There isn't enough free memory for this model. Close other apps, or pick a smaller model under Model.":
      "Er is niet genoeg vrij geheugen voor dit model. Sluit andere apps, of kies een kleiner model onder Model.",
    "The disk is full. Free up some space, then try again.": "De schijf is vol. Maak wat ruimte vrij en probeer het opnieuw.",
    "The AI engine (Ollama) isn't running. Starting it now; try again in a few seconds.":
      "De AI-motor (Ollama) draait niet. Hij wordt nu gestart; probeer het over een paar seconden opnieuw.",
    "The AI engine took too long to answer. Try again, or pick a faster model under Model.":
      "De AI-motor deed er te lang over. Probeer het opnieuw, of kies een sneller model onder Model.",
    "The AI engine stopped. Starting it again.": "De AI-motor is gestopt. Hij wordt opnieuw gestart.",
    "The internet connection dropped.": "De internetverbinding viel weg.",
    "This version of the app can't download the AI engine. Install Ollama from ollama.com.":
      "Deze versie van de app kan de AI-motor niet downloaden. Installeer Ollama via ollama.com.",
    "The AI engine download was damaged in transit. Try again.": "De download van de AI-motor is onderweg beschadigd. Probeer het opnieuw.",
    "Couldn't unpack the AI engine: that needs the zstd program. Install it (for example sudo apt install zstd, or sudo dnf install zstd) and try again.":
      "De AI-motor kon niet worden uitgepakt: daarvoor is het programma zstd nodig. Installeer het (bijvoorbeeld sudo apt install zstd, of sudo dnf install zstd) en probeer het opnieuw.",
    "That library pack isn't available. Check the internet connection.": "Dat bibliotheekpakket is niet beschikbaar. Controleer de internetverbinding.",
    "Couldn't swap in the new library. Close any window showing the library folder, then try again.":
      "De nieuwe bibliotheek kon niet worden geplaatst. Sluit vensters die de bibliotheekmap tonen en probeer het opnieuw.",
    "Couldn't move the library. Close any window showing its folder, then try again.":
      "De bibliotheek kon niet worden verplaatst. Sluit vensters die de map tonen en probeer het opnieuw.",
    "Pick a folder.": "Kies een map.",
    "That folder doesn't exist (is the drive plugged in?).": "Die map bestaat niet (is de schijf aangesloten?).",
    "Survival LLM can't save to that folder. Pick another one.": "Survival LLM kan niet opslaan in die map. Kies een andere.",
    "There's already a folder called Survival LLM Library there. Pick another folder.":
      "Daar staat al een map met de naam Survival LLM Library. Kies een andere map.",
    "That folder is inside the library itself. Pick a folder outside it.": "Die map zit in de bibliotheek zelf. Kies een map daarbuiten.",
    "The update was damaged in transit. Try again.": "De update is onderweg beschadigd. Probeer het opnieuw.",
    "The update didn't pass macOS's signature check, so it wasn't installed.": "De update doorstond de handtekeningcontrole van macOS niet en is niet geïnstalleerd.",
    "The update didn't contain the app, so it wasn't installed.": "De update bevatte de app niet en is niet geïnstalleerd.",
    "That file isn't in the folder any more.": "Dat bestand staat niet meer in de map.",
    "Couldn't move it to the Trash.": "Het kon niet naar de prullenbak worden verplaatst.",
    "Couldn't move it to the Recycle Bin.": "Het kon niet naar de Prullenbak worden verplaatst.",
    "Another library download or move is running. Wait for it to finish.": "Er loopt al een andere bibliotheekdownload of -verplaatsing. Wacht tot die klaar is.",
    "Your files are still being read. Try again in a moment.": "Je bestanden worden nog gelezen. Probeer het zo opnieuw.",
    "The file you're updating isn't in the folder any more. Add this one instead.":
      "Het bestand dat je bijwerkt staat niet meer in de map. Voeg dit bestand in plaats daarvan toe.",
    "This file is too big (over 4 GB).": "Dit bestand is te groot (meer dan 4 GB).",
    "There isn't enough free disk space for this file.": "Er is niet genoeg vrije schijfruimte voor dit bestand.",
    "Couldn't move the old version to the Trash.": "De oude versie kon niet naar de prullenbak worden verplaatst.",
    "Couldn't move the old version to the Recycle Bin.": "De oude versie kon niet naar de Prullenbak worden verplaatst.",
  };

  // [pattern, replacement]: replacement is a string ($1...) or a function of the match's groups.
  const PATTERNS = [
    // Library window: downloading the installed pack again, extra sources
    [/^Download (.+) again \(([\d.]+ GB)\)$/, (m, n, gb) => `Download ${name(n)} opnieuw (${gb})`],
    [/^Downloading (.+) again$/, (m, n) => `Bezig met opnieuw downloaden: ${name(n)}`],
    [/^Adding (.+) to the library…$/, "$1 wordt aan de bibliotheek toegevoegd…"],
    [/^Downloading ([^…]+)…$/, "Bezig met downloaden: $1…"],
    [new RegExp(`^In your library: ${N} articles\\.$`), "In je bibliotheek: $1 artikelen."],
    [/^Add ([A-Z][^.]{0,40})$/, "$1 toevoegen"],
    [/^The website is busy \(too many downloads from this internet connection\)\. Try again in about (\d+) minutes\.$/,
      "De website is druk (te veel downloads vanaf deze internetverbinding). Probeer het over ongeveer $1 minuten opnieuw."],
    [/^Sources in this library \((\d+)\)$/, "Bronnen in deze bibliotheek ($1)"],
    [/^The website answered with an error \(HTTP (\d+)\)\. Try again later\.$/, "De website gaf een fout (HTTP $1). Probeer het later opnieuw."],
    [/^Couldn't add it to the library \((.+)\)\. Is the library on a read-only drive\?$/,
      "Het kon niet aan de bibliotheek worden toegevoegd ($1). Staat de bibliotheek op een alleen-lezen schijf?"],
    [/^(.+) had no articles\. Its website may have changed\.$/, "$1 had geen artikelen. De website is misschien veranderd."],
    [/^Setting up: (\d+)% downloaded$/, "Installatie: $1% gedownload"],
    [/^Getting (.+) ready…$/, "$1 wordt klaargemaakt…"],
    [new RegExp(`^${N} articles$`), "$1 artikelen"],
    [new RegExp(`^\\+ ${N} of your files$`), "+ $1 van je bestanden"],
    [/^by (.+?)\. (.+)$/, (m, maker, blurb) => `van ${maker}. ${tr(blurb) || blurb}`],
    [/^by (.+)$/, "van $1"],
    [/^Now using (.+)\.$/, "Nu met $1."],
    [/^slow here: needs about (\d+) GB of graphics memory, the card has (\d+) GB$/i,
      (m, need, has) => `${m[0] === "S" ? "T" : "t"}raag hier: heeft ongeveer ${need} GB videogeheugen nodig, de kaart heeft ${has} GB`],
    [/^slow here: the AI engine can't use this computer's graphics card$/i,
      (m) => `${m[0] === "S" ? "T" : "t"}raag hier: de AI-motor kan de videokaart van deze computer niet gebruiken`],
    [/^needs (\d+) GB of memory \(RAM\)$/, "heeft $1 GB geheugen (RAM) nodig"],
    [/^needs (\d+) GB of memory \(RAM\); this computer has (\d+) GB$/, "heeft $1 GB geheugen (RAM) nodig; deze computer heeft $2 GB"],
    [/^([\d.]+) GB download$/, "$1 GB downloaden"],
    [/^Download ([\d.]+) GB$/, "$1 GB downloaden"],
    [/^Download ([\d.]+) GB: (.+)$/, "$1 GB downloaden: $2"],
    [/^Downloading (.+)$/, (m, what) => `Bezig met downloaden: ${name(what)}`],
    [/^([\d.]+)(?: GB)? of ([\d.]+) GB$/, "$1 van $2 GB"],
    [/^Needs (\d+) GB free disk; (\d+) GB free$/, "Heeft $1 GB vrije schijfruimte nodig; $2 GB vrij"],
    [/^This computer has (\d+) GB of memory \(RAM\)\.(.*)$/, (m, ram, gpu) => {
      const g = gpuNL(gpu);
      return g == null ? null : `Deze computer heeft ${ram} GB geheugen (RAM).${g}`;
    }],
    [/^This (.+?) computer has (\d+) GB of memory \(RAM\) and (\d+) GB of free disk space\.( (?:Graphics card: .+? with \d+ GB of memory, (?:which the AI uses|which the AI engine can't use, so models run from main memory)|No graphics card found, so models run from main memory)\.)? Bigger models know more but need more memory and are slower\. Download while you have internet, and leave Survival LLM open until it finishes; an interrupted download picks up where it left off\.(?: AI engine: Ollama (\S+), (built into Survival LLM|the Ollama app running on this computer)\.)?$/,
      (m, os, ram, disk, gpu, ver, which) => `Deze ${os}-computer heeft ${ram} GB geheugen (RAM) en ${disk} GB vrije schijfruimte.`
        + (gpu ? gpuNL(gpu) : "") + " "
        + "Grotere modellen weten meer, maar hebben meer geheugen nodig en zijn trager. Download zolang je internet hebt, en laat "
        + "Survival LLM open tot het klaar is; een onderbroken download gaat verder waar hij was."
        + (ver ? ` AI-motor: Ollama ${ver}, ${which === "built into Survival LLM" ? "ingebouwd in Survival LLM" : "de Ollama-app op deze computer"}.` : "")],
    [/^(.+) is already downloading\.$/, "$1 wordt al gedownload."],
    [new RegExp(`^Already on this computer: ${N} articles\\.$`), "Staat al op deze computer: $1 artikelen."],
    [/^Already on this computer: (.+)\. You can change it any time with Model at the top\.$/,
      "Staat al op deze computer: $1. Je kunt het altijd wijzigen met Model bovenaan."],
    [new RegExp(`^${T} to download$`), (m, t) => `${time(t)} downloaden`],
    [/^needs (\d+) GB free while it installs$/, "heeft $1 GB vrij nodig tijdens het installeren"],
    [/^Needs (\d+) GB of free disk space; this computer has (\d+) GB$/, "Heeft $1 GB vrije schijfruimte nodig; deze computer heeft $2 GB"],
    [/^Needs (\d+) GB of memory and this computer has (\d+) GB, so answers will be slow$/,
      "Heeft $1 GB geheugen nodig en deze computer heeft $2 GB, dus antwoorden zijn traag"],
    [new RegExp(`^${T} to download \\(seconds in this preview: it's on this Mac\\)$`),
      (m, t) => `${time(t)} downloaden (seconden in deze proefversie: hij staat al op deze Mac)`],
    [/^None of the AI models fits on this computer \((\d+) GB of memory, (\d+) GB of free disk space\)\. You can still download the library and search it yourself\.$/,
      "Geen van de AI-modellen past op deze computer ($1 GB geheugen, $2 GB vrije schijfruimte). Je kunt wel de bibliotheek downloaden en er zelf in zoeken."],
    [/^Other AI models \((\d+)\)$/, "Andere AI-modellen ($1)"],
    [/^The AI models \((\d+)\)$/, "De AI-modellen ($1)"],
    [/^Includes the AI engine that runs it on this computer \((.+)\)\.$/, "Inclusief de AI-motor die hem op deze computer draait ($1)."],
    [/^That needs about (\d+) GB of free disk space while it installs, and this computer has (\d+) GB\. Pick (Essentials or )?a smaller AI, or free up some space\.$/,
      (m, a, b, ess) => `Daarvoor is tijdens het installeren ongeveer ${a} GB vrije schijfruimte nodig, en deze computer heeft ${b} GB. `
        + `Kies ${ess ? "Basis of " : ""}een kleinere AI, of maak ruimte vrij.`],
    [new RegExp(`^${T}$`), (m, t) => time(t)],
    [/^Library: (.+)$/, (m, n) => `Bibliotheek: ${name(n)}`],
    [/^AI: (.+)$/, "AI: $1"],
    [new RegExp(`^Ready: ${N} articles\\.$`), "Klaar: $1 artikelen."],
    [new RegExp(`^${T} left$`), (m, t) => `nog ${time(t)}`],
    [new RegExp(`^${T} left in all$`), (m, t) => `nog ${time(t)} in totaal`],
    [/^(.*) Trying again in (\d+) s\.$/, (m, err, s) => `${tr(err) || err} Nieuwe poging over ${s} s.`],
    [new RegExp(`^Next: ([\\d.]+ GB), ${T}$`), (m, gb, t) => `Hierna: ${gb}, ${time(t)}`],
    [/^Setup download, (\d+)%$/, "Installatiedownload, $1%"],
    [/^(\d+)%$/, "$1%"],
    [/^(.+) is installed$/, (m, n) => `${name(n)} is geïnstalleerd`],
    [new RegExp(`^${N} articles from (\\d+) sources\\.$`), "$1 artikelen uit $2 bronnen."],
    [/^Switch to (.+?)(?: \(([\d.]+ GB)\))?$/, (m, n, gb) => `Wissel naar ${name(n)}${gb ? ` (${gb})` : ""}`],
    [/^Download (.+?)(?: \(([\d.]+ GB)\))?$/, (m, n, gb) => (NAMES[n] ? `Download ${name(n)}${gb ? ` (${gb})` : ""}` : null)],
    [/^(.+) download$/, (m, n) => (NAMES[n] ? `${name(n)} downloaden` : null)],
    [new RegExp(`^([\\d.]+ GB) download, ${T} on typical home internet\\. Needs (\\d+) GB free while it installs; this computer has (\\d+) GB\\.( Your current library keeps working until the new one is ready, then the new one replaces it\\.)?$`),
      (m, gb, t, need, have, cur) => `${gb} downloaden, ${time(t)} met gewoon thuisinternet. Heeft ${need} GB vrij nodig tijdens het `
        + `installeren; deze computer heeft ${have} GB.${cur ? " Je huidige bibliotheek blijft werken tot de nieuwe klaar is, en wordt dan vervangen." : ""}`],
    [new RegExp(`^(.+): ${N} articles ·$`), (m, n, a) => `${name(n)}: ${a} artikelen ·`],
    [/^(.+) is working on it… (\d+) s$/, "$1 is bezig… $2 s"],
    [/^(.+)'s reasoning so far$/, "Redeneren van $1 tot nu toe"],
    [/^(.+)'s reasoning( before it answered| before you stopped it| so far)? · (\d+) s of thinking$/,
      (m, who, until, s) => `Redeneren van ${who}${{ " before it answered": " voordat hij antwoordde",
        " before you stopped it": " voordat je hem stopte", " so far": " tot nu toe" }[until] || ""} · ${s} s nagedacht`],
    [/^(.+) answered without reasoning first, because Reasoning is set to Off\. Set it to Short or more before you ask, and it thinks first\.$/,
      "$1 antwoordde zonder eerst na te denken, omdat redeneren uit staat. Zet het op Kort of meer voordat je iets vraagt, dan denkt hij eerst na."],
    [/^(.+) doesn't reason before it answers, so there's nothing to show\.$/, "$1 denkt niet na voordat hij antwoordt, dus er is niets te laten zien."],
    [/^the library for “(.*)”$/, "de bibliotheek naar “$1”"],
    [/^Searched the library: “(.*)”$/, "Bibliotheek doorzocht: “$1”"],
    [/^Its thinking reached the limit \(([\d.,]+) tokens\), so it answered from what it had\.$/,
      "Het redeneren bereikte de grens ($1 tokens), dus antwoordde hij met wat hij had."],
    [/^(.+) was stopped after (\d+) s because the answer reached the length limit\. Keep going, or raise the limit below\.$/,
      "$1 is na $2 s gestopt omdat het antwoord de lengtegrens bereikte. Ga verder, of verhoog de grens hieronder."],
    [/^(.+) didn't finish an answer\. Try asking again, or open the articles it read below\.$/,
      "$1 maakte geen antwoord af. Vraag het opnieuw, of open hieronder de artikelen die hij las."],
    [/^(.+) didn't finish an answer\. Try asking again, or open one of the search results below\.$/,
      "$1 maakte geen antwoord af. Vraag het opnieuw, of open hieronder een van de zoekresultaten."],
    [/^(.+) didn't write an answer\. Try asking again\.$/, "$1 schreef geen antwoord. Vraag het opnieuw."],
    [/^Answered by (.+) in (\d+) s$/, "Beantwoord door $1 in $2 s"],
    [/^(\d+) tokens at (\d+) tokens per second$/, "$1 tokens met $2 tokens per seconde"],
    [/^Answer ready from (.+)\.$/, "Antwoord van $1 is klaar."],
    [/^Couldn't get an answer: (.*)$/, (m, e) => `Kon geen antwoord krijgen: ${tr(e) || e}`],
    [/^How it found this \((\d+) steps?\)$/, (m, n) => `Hoe hij dit vond (${n} ${n === "1" ? "stap" : "stappen"})`],
    [/^Other search results \((\d+)\)$/, "Andere zoekresultaten ($1)"],
    [/^Remembered: “(.*)”$/s, "Onthouden: “$1”"],
    [/^Updated a memory: “(.*)”$/s, "Herinnering bijgewerkt: “$1”"],
    [/^Forgot: “(.*)”$/s, "Vergeten: “$1”"],
    [/^Memory is full, so it didn't save “(.*)”\. Delete notes you don't need in Memory\.$/s,
      "Het geheugen is vol, dus “$1” is niet opgeslagen. Wis notities die je niet nodig hebt in Geheugen."],
    [/^Undone: it won't remember “(.*)”$/s, "Ongedaan gemaakt: hij onthoudt “$1” niet"],
    [/^Undone: back to “(.*)”$/s, "Ongedaan gemaakt: terug naar “$1”"],
    [/^Undone: it remembers “(.*)” again$/s, "Ongedaan gemaakt: hij onthoudt “$1” weer"],
    [/^(.+)\. Couldn't undo it here, maybe because the note was edited since; change it in Memory\.$/s,
      (m, said) => `${tr(said) || said}. Dat kon hier niet ongedaan worden gemaakt, misschien omdat de notitie intussen is bewerkt; wijzig het in Geheugen.`],
    [/^(\d+) results for “(.*)”$/, "$1 resultaten voor “$2”"],
    [/^Nothing found for “(.*)”\. Try fewer or different words\.$/, "Niets gevonden voor “$1”. Probeer minder of andere woorden."],
    [/^Adding a file…$/, "Bezig met toevoegen van een bestand…"],
    [/^Adding (\d+) files…$/, "Bezig met toevoegen van $1 bestanden…"],
    [/^Reading (.+) \((\d+) of (\d+)\)… Big files take a minute or two\.$/, "Bezig met lezen van $1 ($2 van $3)… Grote bestanden duren een minuut of twee."],
    [/^Added (.+?)(?: and (\d+) more)?\.$/, (m, names, more) => `Toegevoegd: ${names}${more ? ` en nog ${more}` : ""}.`],
    [/^You already have a file called “(.+)”\. Replace it with this one\?$/, "Je hebt al een bestand met de naam “$1”. Wil je het vervangen door dit bestand?"],
    [/^They're kept in (.+)\. Files you put in that folder, or change there, are picked up on their own\.$/,
      "Ze worden bewaard in $1. Bestanden die je in die map zet of daar wijzigt, worden vanzelf opgepikt."],
    [/^(.+) is already in your files\.$/, "$1 staat al in je bestanden."],
    [/^Replaced (.+) with the new version\. The old one is in the (Trash|Recycle Bin)\.$/,
      (m, f, b) => `${f} is vervangen door de nieuwe versie. De oude staat in de ${bin(b)}.`],
    [/^Click again to move it to the (Trash|Recycle Bin)$/, (m, b) => `Klik nogmaals om het naar de ${bin(b)} te verplaatsen`],
    [/^Removed (.+)\. It's in the (Trash|Recycle Bin) if you want it back\.$/,
      (m, f, b) => `${f} is verwijderd. Het staat in de ${bin(b)} als je het terug wilt.`],
    [/^(.+) is a folder\. To add a whole folder, click Open the folder and put it there\.$/,
      "$1 is een map. Om een hele map toe te voegen, klik je op Open de map en zet je hem daar neer."],
    [/^Survival LLM (\S+) is available\.?$/, (m, v) => `Survival LLM ${v} is beschikbaar${m.endsWith(".") ? "." : ""}`],
    [/^A newer library is available\.(?: (.*?))? It's a (.+) download, and yours keeps working until it's in\.$/,
      (m, notes, sz) => `Er is een nieuwere bibliotheek.${notes ? ` ${tr(notes) || notes}` : ""} Het is een download van ${sz}, en de jouwe blijft werken tot hij erin staat.`],
    [/^The last update couldn't be installed \((.+)\)\. You still have version (\S+)\.$/,
      (m, why, v) => `De laatste update kon niet worden geïnstalleerd (${tr(why) || why}). Je hebt nog versie ${v}.`],
    [/^You have (\S+)\.(?: Released (.+?)\.)? (.+) download\.$/,
      (m, v, d, sz) => `Je hebt ${v}.${d ? ` Uitgebracht op ${d}.` : ""} Download van ${sz}.`],
    [/^Downloading Survival LLM (\S+)$/, "Bezig met downloaden van Survival LLM $1"],
    [/^Couldn't check for updates \(no internet\?\)\. Survival LLM works fine without them\. You have version (\S+)\.$/,
      "Kon niet zoeken naar updates (geen internet?). Survival LLM werkt prima zonder. Je hebt versie $1."],
    [/^Couldn't check for updates right now\. Survival LLM works fine without them\. You have version (\S+)\.$/,
      "Kon nu niet zoeken naar updates. Survival LLM werkt prima zonder. Je hebt versie $1."],
    [/^You have the latest version of Survival LLM \((\S+)\)\.$/, "Je hebt de nieuwste versie van Survival LLM ($1)."],
    [/^(.+), from (.+)\.$/, (m, label, d) => { const n = label.split(":")[0]; return NAMES[n] ? `${name(n)}, van ${d}.` : null; }],
    [/^Update the library \((.+)\)$/, "Werk de bibliotheek bij ($1)"],
    [/^Last checked (.+)\.$/, "Laatst gekeken: $1."],
    [/^Dev copy: (.+)$/, "Ontwikkelkopie: $1"],
    [/^dev copy: (.+)$/, "ontwikkelkopie: $1"],
    [new RegExp(`^(\\d+) notes? · ${N} of ${N} characters$`),
      (m, n, a, b) => `${n} ${n === "1" ? "notitie" : "notities"} · ${a} van ${b} tekens`],
    [/^(Saved\. Used from your next question\.|Deleted all notes\.)(?: Also kept (a note|\d+ notes) the AI saved while you were editing\.)?(?: Left out (a note|\d+ notes) the AI deleted or changed meanwhile\.)?$/,
      (m, done, kept, dropped) => {
        const n = (k) => (k === "a note" ? "één notitie" : k.replace("notes", "notities"));
        return tr(done) + (kept ? ` Ook ${n(kept)} bewaard die de AI opsloeg terwijl je bewerkte.` : "")
          + (dropped ? ` ${n(dropped).replace(/^./, (c) => c.toUpperCase())} weggelaten die de AI intussen wiste of wijzigde.` : "");
      }],
    // server messages with numbers or paths
    [/^Couldn't save: another program is using (.+)\. Close it and try again\.$/, "Opslaan lukte niet: een ander programma gebruikt $1. Sluit het en probeer het opnieuw."],
    [/^Couldn't save (.+?): (.+)\.$/, "Kon $1 niet opslaan: $2."],
    [/^The AI engine reported a problem: (.+)\.$/, "De AI-motor meldde een probleem: $1."],
    [/^Something went wrong: (.+)$/, "Er ging iets mis: $1"],
    [/^The download site answered with an error \(HTTP (\d+)\)\.$/, "De downloadsite antwoordde met een fout (HTTP $1)."],
    [/^That drive can't hold files this big(.*?)\. It's probably formatted as FAT32: pick another (.*)$/,
      "Die schijf kan zulke grote bestanden niet bevatten$1. Hij is waarschijnlijk als FAT32 geformatteerd: kies een andere plek."],
    [/^That drive is read-only(.*)\. Pick another place for the library\.$/, "Die schijf is alleen-lezen$1. Kies een andere plek voor de bibliotheek."],
    [/^Survival LLM can't save there(.*)\. If the library is on a drive, plug it in; or move the library somewhere else \(Library window\)\.$/,
      "Survival LLM kan daar niet opslaan$1. Staat de bibliotheek op een schijf, sluit die dan aan; of verplaats de bibliotheek (Bibliotheekvenster)."],
    [/^Couldn't save the download(.*?): (.+)\.$/, "Kon de download niet opslaan$1: $2."],
    [/^Download failed: (.+)$/, "Download mislukt: $1"],
    [/^Not enough free disk space: installing (the AI engine|this pack) needs about (\d+) GB free, and this computer has (\d+) GB\.$/,
      (m, what, a, b) => `Niet genoeg vrije schijfruimte: ${what === "the AI engine" ? "de AI-motor" : "dit pakket"} installeren vraagt ongeveer ${a} GB vrij, en deze computer heeft ${b} GB.`],
    [/^Not enough free disk space for the update: it needs about (\d+) GB free, and this computer has (\d+) GB\.$/,
      "Niet genoeg vrije schijfruimte voor de update: die vraagt ongeveer $1 GB vrij, en deze computer heeft $2 GB."],
    [/^The library's folder \((.+)\) has other files in it too, so Survival LLM won't replace it\. Move the library to a folder of its own first \(Library window, Move it…\)\.$/,
      "In de map van de bibliotheek ($1) staan ook andere bestanden, dus Survival LLM vervangt hem niet. Verplaats de bibliotheek eerst naar een eigen map (Bibliotheekvenster, Verplaats hem…)."],
    [/^Part (\d+) of (\d+) was damaged in transit\. Try again to re-download it\.$/, "Deel $1 van $2 is onderweg beschadigd. Probeer opnieuw om het opnieuw te downloaden."],
    [/^Not enough free space there: the library needs about (\d+) GB, and that drive has (\d+) GB free\.$/,
      "Niet genoeg vrije ruimte daar: de bibliotheek vraagt ongeveer $1 GB, en die schijf heeft $2 GB vrij."],
    [/^That's more than memory holds \(([\d.,]+) characters\)\. Shorten some notes, or put longer things in Your files\.$/,
      "Dat is meer dan het geheugen kan bevatten ($1 tekens). Maak notities korter, of zet langere dingen in Je bestanden."],
    [/^Wait until (.+) has finished, then update\.$/, "Wacht tot $1 klaar is en werk dan bij."],
    [/^Couldn't save this file \((.+)\)\.$/, "Dit bestand kon niet worden opgeslagen ($1)."],
    [/^You already have a file called (.+)\.$/, "Je hebt al een bestand met de naam $1."],
    [/^This model needs a newer AI engine than the (?:Ollama app )?(?:Ollama )?running on this computer(.*)$/,
      "Dit model heeft een nieuwere AI-motor nodig dan de Ollama op deze computer$1"],
    // last: a library pack's description, "<about>. 494,574 articles."
    [new RegExp(`^(.+?)\\.(?: ${N} articles\\.)?$`), (m, about, n) => {
      const t = tr(about);
      return t ? `${t}.${n ? ` ${n} artikelen.` : ""}` : null;
    }],
  ];

  return { exact: EXACT, patterns: PATTERNS };
});
