"""Our own texts for the battery and charging errors, translated (4.5.0).

ONLY 101-121 ARE OURS. Every other error text comes from iRobot's app
for the robot's generation (roombapy-prime: `vendor_errors_classic` for
Classic, `vendor_errors` for Prime; see `get_localized_error_entry`).
These seventeen stay ours because the Classic app shows nothing specific
for them -- "Charging error", "@val has a battery error.", or "Follow our
step-by-step guide" -- while iRobot's own help page for each code says
what is wrong (Classic 980 pages "Charging Error 1-9, 19, 21", Prime
pages 10601-10622; see `OWN_ERROR_SOURCES` in const.py). The texts are
written for this project from those pages, not copied.

English is in `ERROR_CATALOGUE` (const.py). A language or field missing
here falls back to English, never to an empty string.
"""

from typing import Final

# code -> language -> (label, description, action)
_TEXTS: Final[dict[int, dict[str, tuple[str, str, str]]]] = {
    101: {
        "de": ("Batterie nicht verbunden", "Die Batterie wird nicht erkannt.", "Prüfen, ob die Batterie fest sitzt. Bei Bedarf Support kontaktieren."),
        "es": ("Batería no conectada", "No se detecta la batería.", "Compruebe que la batería esté bien asentada. Contacte con soporte si es necesario."),
        "fr": ("Batterie non connectée", "La batterie n'est pas détectée.", "Vérifiez que la batterie est bien en place. Contactez le support si nécessaire."),
        "it": ("Batteria non collegata", "La batteria non viene rilevata.", "Verificare che la batteria sia ben inserita. Contattare l'assistenza se necessario."),
        "nl": ("Batterij niet aangesloten", "De batterij wordt niet gedetecteerd.", "Controleer of de batterij goed is geplaatst. Neem indien nodig contact op met de support."),
        "pl": ("Akumulator niepodłączony", "Akumulator nie został wykryty.", "Sprawdź, czy akumulator jest dobrze osadzony. W razie potrzeby skontaktuj się z pomocą techniczną."),
        "pt": ("Bateria não ligada", "A bateria não é detetada.", "Verifique se a bateria está bem encaixada. Contacte o suporte se necessário."),
    },
    102: {
        "de": ("Batterie lädt nicht", "Ein Fehler wurde erkannt, die Batterie wird nicht geladen.", "Batterie herausnehmen und wieder einsetzen. War der Roboter in der Nähe von Flüssigkeit, auf Wasserschaden prüfen. Bleibt der Fehler, iRobot-Support kontaktieren."),
        "es": ("La batería no se carga", "Se ha detectado un fallo y la batería no se carga.", "Retire la batería y vuelva a colocarla. Si el robot ha estado cerca de líquidos, compruebe si hay daños por agua. Si el error persiste, contacte con el soporte de iRobot."),
        "fr": ("La batterie ne charge pas", "Une erreur a été détectée et la batterie ne charge pas.", "Retirez la batterie et remettez-la en place. Si le robot a été en contact avec un liquide, vérifiez l'absence de dégâts des eaux. Si l'erreur persiste, contactez le support iRobot."),
        "it": ("La batteria non si ricarica", "È stato rilevato un errore e la batteria non si ricarica.", "Rimuovere la batteria e reinserirla. Se il robot è stato vicino a liquidi, verificare la presenza di danni da acqua. Se l'errore persiste, contattare l'assistenza iRobot."),
        "nl": ("Batterij laadt niet op", "Er is een fout gedetecteerd en de batterij laadt niet op.", "Haal de batterij eruit en plaats hem terug. Is de robot in de buurt van vloeistof geweest, controleer dan op waterschade. Blijft de fout bestaan, neem contact op met iRobot-support."),
        "pl": ("Akumulator się nie ładuje", "Wykryto błąd i akumulator się nie ładuje.", "Wyjmij akumulator i włóż go ponownie. Jeśli robot miał kontakt z cieczą, sprawdź, czy nie został zalany. Jeśli błąd nie ustępuje, skontaktuj się z pomocą techniczną iRobot."),
        "pt": ("A bateria não carrega", "Foi detetado um erro e a bateria não está a carregar.", "Retire a bateria e volte a colocá-la. Se o robô esteve perto de líquidos, verifique se há danos causados pela água. Se o erro persistir, contacte o suporte iRobot."),
    },
    103: {
        "de": ("Ladesystem defekt", "Das Ladesystem des Roboters funktioniert nicht richtig.", "iRobot-Support kontaktieren."),
        "es": ("Fallo del sistema de carga", "El sistema de carga del robot no funciona correctamente.", "Contacte con el soporte de iRobot."),
        "fr": ("Défaut du système de charge", "Le système de charge du robot ne fonctionne pas correctement.", "Contactez le support iRobot."),
        "it": ("Guasto del sistema di ricarica", "Il sistema di ricarica del robot non funziona correttamente.", "Contattare l'assistenza iRobot."),
        "nl": ("Storing in het laadsysteem", "Het laadsysteem van de robot werkt niet goed.", "Neem contact op met iRobot-support."),
        "pl": ("Usterka układu ładowania", "Układ ładowania robota nie działa prawidłowo.", "Skontaktuj się z pomocą techniczną iRobot."),
        "pt": ("Falha no sistema de carregamento", "O sistema de carregamento do robô não está a funcionar corretamente.", "Contacte o suporte iRobot."),
    },
    104: {
        "de": ("Kein Ladestrom", "Es wird kein Ladestrom empfangen.", "Netzkabel und Steckdose der Ladestation prüfen. Ladekontakte reinigen."),
        "es": ("Sin corriente de carga", "No se recibe corriente de carga.", "Compruebe el cable de alimentación y la toma de la base. Limpie los contactos de carga."),
        "fr": ("Aucun courant de charge", "Aucun courant de charge n'est reçu.", "Vérifiez le câble d'alimentation et la prise de la base. Nettoyez les contacts de charge."),
        "it": ("Nessuna corrente di ricarica", "Non viene ricevuta alcuna corrente di ricarica.", "Controllare il cavo di alimentazione e la presa della base. Pulire i contatti di ricarica."),
        "nl": ("Geen laadstroom", "Er wordt geen laadstroom ontvangen.", "Controleer de voedingskabel en het stopcontact van het basisstation. Reinig de laadcontacten."),
        "pl": ("Brak prądu ładowania", "Robot nie otrzymuje prądu ładowania.", "Sprawdź kabel zasilający i gniazdko stacji. Wyczyść styki ładowania."),
        "pt": ("Sem corrente de carregamento", "Não está a ser recebida corrente de carregamento.", "Verifique o cabo de alimentação e a tomada da base. Limpe os contactos de carregamento."),
    },
    105: {
        "de": ("Ladestrom zu niedrig", "Der Ladestrom liegt unter dem erwarteten Niveau.", "Ladekontakte am Roboter und an der Ladestation reinigen."),
        "es": ("Corriente de carga demasiado baja", "La corriente de carga está por debajo del nivel esperado.", "Limpie los contactos de carga en el robot y la base."),
        "fr": ("Courant de charge trop faible", "Le courant de charge est inférieur au niveau attendu.", "Nettoyez les contacts de charge sur le robot et la base."),
        "it": ("Corrente di ricarica troppo bassa", "La corrente di ricarica è inferiore al livello previsto.", "Pulire i contatti di ricarica sul robot e sulla base."),
        "nl": ("Laadstroom te laag", "De laadstroom ligt onder het verwachte niveau.", "Reinig de laadcontacten op de robot en het basisstation."),
        "pl": ("Zbyt niski prąd ładowania", "Prąd ładowania jest niższy niż oczekiwany.", "Wyczyść styki ładowania na robocie i na stacji."),
        "pt": ("Corrente de carregamento demasiado baixa", "A corrente de carregamento está abaixo do nível esperado.", "Limpe os contactos de carregamento no robô e na base."),
    },
    106: {
        "de": ("Batterie zu warm", "Die Batterietemperatur ist zu hoch zum Laden.", "Roboter an einen kühleren Ort bringen und vor dem Laden warten."),
        "es": ("Batería demasiado caliente", "La temperatura de la batería es demasiado alta para cargar.", "Mueva el robot a un lugar más fresco y espere antes de cargar."),
        "fr": ("Batterie trop chaude", "La température de la batterie est trop élevée pour charger.", "Déplacez le robot vers un endroit plus frais et attendez avant de charger."),
        "it": ("Batteria troppo calda", "La temperatura della batteria è troppo alta per la ricarica.", "Spostare il robot in un luogo più fresco e attendere prima di ricaricare."),
        "nl": ("Batterij te warm", "De batterijtemperatuur is te hoog om op te laden.", "Verplaats de robot naar een koelere plek en wacht voordat u oplaadt."),
        "pl": ("Akumulator zbyt ciepły", "Temperatura akumulatora jest zbyt wysoka, aby go ładować.", "Przenieś robota w chłodniejsze miejsce i odczekaj przed ładowaniem."),
        "pt": ("Bateria demasiado quente", "A temperatura da bateria está demasiado alta para carregar.", "Mova o robô para um local mais fresco e aguarde antes de carregar."),
    },
    107: {
        "de": ("Batterie zu kalt", "Die Batterie ist zu kalt zum Laden.", "Roboter und Station in einen Raum mit normaler Zimmertemperatur (etwa 15–23 °C) bringen und dort laden."),
        "es": ("Batería demasiado fría", "La batería está demasiado fría para cargar.", "Lleve el robot y la base a una habitación a temperatura ambiente normal (unos 15–23 °C) y cárguelo allí."),
        "fr": ("Batterie trop froide", "La batterie est trop froide pour être chargée.", "Placez le robot et sa base dans une pièce à température ambiante normale (environ 15–23 °C) et chargez-le là."),
        "it": ("Batteria troppo fredda", "La batteria è troppo fredda per la ricarica.", "Portare il robot e la base in una stanza a temperatura ambiente normale (circa 15–23 °C) e ricaricarlo lì."),
        "nl": ("Batterij te koud", "De batterij is te koud om op te laden.", "Zet de robot en het basisstation in een ruimte op normale kamertemperatuur (ongeveer 15–23 °C) en laad hem daar op."),
        "pl": ("Akumulator zbyt zimny", "Akumulator jest zbyt zimny, aby go ładować.", "Przenieś robota i stację do pomieszczenia o normalnej temperaturze pokojowej (ok. 15–23 °C) i tam go naładuj."),
        "pt": ("Bateria demasiado fria", "A bateria está demasiado fria para carregar.", "Leve o robô e a base para uma divisão à temperatura ambiente normal (cerca de 15–23 °C) e carregue-o aí."),
    },
    108: {
        "de": ("Batterie lädt nicht", "Die Batterie lädt nicht, meist wegen ihrer Temperatur oder weil sie keine Original-Batterie von iRobot ist.", "Den Roboter bei Zimmertemperatur laden und eine Original-Batterie von iRobot verwenden."),
        "es": ("La batería no se carga", "La batería no se carga, normalmente por su temperatura o porque no es una batería original de iRobot.", "Cargue el robot a temperatura ambiente y utilice una batería original de iRobot."),
        "fr": ("La batterie ne charge pas", "La batterie ne charge pas, généralement à cause de sa température ou parce qu'il ne s'agit pas d'une batterie d'origine iRobot.", "Chargez le robot à température ambiante et utilisez une batterie d'origine iRobot."),
        "it": ("La batteria non si ricarica", "La batteria non si ricarica, di solito per la sua temperatura o perché non è una batteria originale iRobot.", "Ricaricare il robot a temperatura ambiente e utilizzare una batteria originale iRobot."),
        "nl": ("Batterij laadt niet op", "De batterij laadt niet op, meestal door de temperatuur of omdat het geen originele iRobot-batterij is.", "Laad de robot op kamertemperatuur op en gebruik een originele iRobot-batterij."),
        "pl": ("Akumulator się nie ładuje", "Akumulator się nie ładuje, zwykle z powodu temperatury lub dlatego, że nie jest to oryginalny akumulator iRobot.", "Ładuj robota w temperaturze pokojowej i używaj oryginalnego akumulatora iRobot."),
        "pt": ("A bateria não carrega", "A bateria não carrega, normalmente devido à temperatura ou por não ser uma bateria original iRobot.", "Carregue o robô à temperatura ambiente e utilize uma bateria original iRobot."),
    },
    109: {
        "de": ("Dauerhafter Batteriefehler", "Die Batterie meldet einen Fehler, der nicht von selbst verschwindet.", "Batterie mindestens 15 Minuten herausnehmen und wieder einsetzen. Kommt der Fehler wieder, die Batterie ersetzen."),
        "es": ("Fallo permanente de la batería", "La batería indica un fallo que no desaparece por sí solo.", "Retire la batería durante al menos 15 minutos y vuelva a colocarla. Si el error vuelve, sustituya la batería."),
        "fr": ("Défaut permanent de la batterie", "La batterie signale un défaut qui ne disparaît pas de lui-même.", "Retirez la batterie pendant au moins 15 minutes, puis remettez-la en place. Si l'erreur revient, remplacez la batterie."),
        "it": ("Guasto permanente della batteria", "La batteria segnala un guasto che non si risolve da solo.", "Rimuovere la batteria per almeno 15 minuti e reinserirla. Se l'errore si ripresenta, sostituire la batteria."),
        "nl": ("Blijvende batterijstoring", "De batterij meldt een storing die niet vanzelf verdwijnt.", "Haal de batterij minstens 15 minuten uit de robot en plaats hem terug. Komt de fout terug, vervang dan de batterij."),
        "pl": ("Trwała usterka akumulatora", "Akumulator zgłasza usterkę, która nie ustępuje sama.", "Wyjmij akumulator na co najmniej 15 minut i włóż go ponownie. Jeśli błąd powróci, wymień akumulator."),
        "pt": ("Falha permanente da bateria", "A bateria indica uma falha que não desaparece sozinha.", "Retire a bateria durante pelo menos 15 minutos e volte a colocá-la. Se o erro voltar, substitua a bateria."),
    },
    110: {
        "de": ("Ungleichgewicht der Batteriezellen", "Die Batteriezellen sind nicht im Gleichgewicht.", "Die Batterie muss ersetzt werden. iRobot-Support kontaktieren."),
        "es": ("Desequilibrio de celdas de la batería", "Las celdas de la batería están desequilibradas.", "Es necesario sustituir la batería. Contacte con el soporte de iRobot."),
        "fr": ("Déséquilibre des cellules de la batterie", "Les cellules de la batterie sont déséquilibrées.", "La batterie doit être remplacée. Contactez le support iRobot."),
        "it": ("Squilibrio delle celle della batteria", "Le celle della batteria sono sbilanciate.", "La batteria deve essere sostituita. Contattare l'assistenza iRobot."),
        "nl": ("Onbalans in de batterijcellen", "De batterijcellen zijn niet in balans.", "De batterij moet worden vervangen. Neem contact op met iRobot-support."),
        "pl": ("Nierównowaga ogniw akumulatora", "Ogniwa akumulatora są niezrównoważone.", "Akumulator wymaga wymiany. Skontaktuj się z pomocą techniczną iRobot."),
        "pt": ("Desequilíbrio das células da bateria", "As células da bateria estão desequilibradas.", "A bateria tem de ser substituída. Contacte o suporte iRobot."),
    },
    111: {
        "de": ("Hardwarefehler der Batterie", "Die Batterie hat einen Hardwarefehler.", "Batterie 15 Minuten herausnehmen und wieder einsetzen. Kommt der Fehler wieder, den iRobot-Support wegen eines Batterieaustauschs kontaktieren."),
        "es": ("Fallo de hardware de la batería", "La batería tiene un fallo de hardware.", "Retire la batería durante 15 minutos y vuelva a colocarla. Si el error vuelve, contacte con el soporte de iRobot para sustituirla."),
        "fr": ("Défaut matériel de la batterie", "La batterie présente un défaut matériel.", "Retirez la batterie pendant 15 minutes, puis remettez-la en place. Si l'erreur revient, contactez le support iRobot pour la remplacer."),
        "it": ("Guasto hardware della batteria", "La batteria presenta un guasto hardware.", "Rimuovere la batteria per 15 minuti e reinserirla. Se l'errore si ripresenta, contattare l'assistenza iRobot per la sostituzione."),
        "nl": ("Hardwarestoring van de batterij", "De batterij heeft een hardwarestoring.", "Haal de batterij 15 minuten uit de robot en plaats hem terug. Komt de fout terug, neem dan contact op met iRobot-support voor vervanging."),
        "pl": ("Usterka sprzętowa akumulatora", "Akumulator ma usterkę sprzętową.", "Wyjmij akumulator na 15 minut i włóż go ponownie. Jeśli błąd powróci, skontaktuj się z pomocą techniczną iRobot w sprawie wymiany."),
        "pt": ("Falha de hardware da bateria", "A bateria tem uma falha de hardware.", "Retire a bateria durante 15 minutos e volte a colocá-la. Se o erro voltar, contacte o suporte iRobot para a substituir."),
    },
    114: {
        "de": ("Interner Batteriefehler", "Ein interner Batteriefehler wurde erkannt.", "iRobot-Support für einen Batterieaustausch kontaktieren."),
        "es": ("Fallo interno de batería", "Se ha detectado un fallo interno de la batería.", "Contacte con el soporte de iRobot para el reemplazo de la batería."),
        "fr": ("Défaillance interne de la batterie", "Une défaillance interne de la batterie a été détectée.", "Contactez le support iRobot pour un remplacement de la batterie."),
        "it": ("Guasto interno batteria", "È stato rilevato un guasto interno della batteria.", "Contattare l'assistenza iRobot per la sostituzione della batteria."),
        "nl": ("Interne batterijstoring", "Er is een interne batterijstoring gedetecteerd.", "Neem contact op met iRobot-support voor batterijvervanging."),
        "pl": ("Wewnętrzna usterka akumulatora", "Wykryto wewnętrzną usterkę akumulatora.", "Skontaktuj się z pomocą techniczną iRobot w sprawie wymiany akumulatora."),
        "pt": ("Falha interna da bateria", "Foi detetada uma falha interna da bateria.", "Contacte o suporte iRobot para substituição da bateria."),
    },
    115: {
        "de": ("Zellenausfall beim Laden", "Eine Batteriezelle ist während eines Ladezyklus ausgefallen.", "iRobot-Support für einen Batterieaustausch kontaktieren."),
        "es": ("Fallo de celda durante la carga", "Una celda de la batería falló durante un ciclo de carga.", "Contacte con el soporte de iRobot para el reemplazo de la batería."),
        "fr": ("Défaillance de cellule pendant la charge", "Une cellule de la batterie a défailli pendant un cycle de charge.", "Contactez le support iRobot pour un remplacement de la batterie."),
        "it": ("Guasto cella durante la ricarica", "Una cella della batteria ha ceduto durante un ciclo di ricarica.", "Contattare l'assistenza iRobot per la sostituzione della batteria."),
        "nl": ("Celstoring tijdens opladen", "Een batterijcel is uitgevallen tijdens een oplaadcyclus.", "Neem contact op met iRobot-support voor batterijvervanging."),
        "pl": ("Awaria ogniwa podczas ładowania", "Podczas ładowania uległo awarii ogniwo akumulatora.", "Skontaktuj się z pomocą techniczną iRobot w sprawie wymiany akumulatora."),
        "pt": ("Falha de célula durante o carregamento", "Uma célula da bateria falhou durante um ciclo de carregamento.", "Contacte o suporte iRobot para substituição da bateria."),
    },
    117: {
        "de": ("Batterie nicht erkannt", "Der Roboter erkennt die Batterie nicht als Original-Batterie von iRobot.", "Eine Original-Batterie von iRobot verwenden."),
        "es": ("Batería no reconocida", "El robot no reconoce la batería como una batería original de iRobot.", "Utilice una batería original de iRobot."),
        "fr": ("Batterie non reconnue", "Le robot ne reconnaît pas la batterie comme une batterie d'origine iRobot.", "Utilisez une batterie d'origine iRobot."),
        "it": ("Batteria non riconosciuta", "Il robot non riconosce la batteria come batteria originale iRobot.", "Utilizzare una batteria originale iRobot."),
        "nl": ("Batterij niet herkend", "De robot herkent de batterij niet als originele iRobot-batterij.", "Gebruik een originele iRobot-batterij."),
        "pl": ("Akumulator nierozpoznany", "Robot nie rozpoznaje akumulatora jako oryginalnego akumulatora iRobot.", "Używaj oryginalnego akumulatora iRobot."),
        "pt": ("Bateria não reconhecida", "O robô não reconhece a bateria como uma bateria original iRobot.", "Utilize uma bateria original iRobot."),
    },
    119: {
        "de": ("Zeitüberschreitung beim Laden", "Der Ladezyklus hat eine Zeitüberschreitung erreicht.", "Ladekontakte der Station prüfen und den Ladezyklus erneut starten."),
        "es": ("Tiempo de carga agotado", "El ciclo de carga agotó el tiempo de espera.", "Compruebe los contactos de la base e intente reiniciar el ciclo de carga."),
        "fr": ("Délai de charge dépassé", "Le cycle de charge a dépassé le délai.", "Vérifiez les contacts de la base et essayez de relancer le cycle de charge."),
        "it": ("Timeout di ricarica", "Il ciclo di ricarica è andato in timeout.", "Controllare i contatti della base e provare a riavviare il ciclo di ricarica."),
        "nl": ("Time-out bij opladen", "De oplaadcyclus kreeg een time-out.", "Controleer de laadcontacten van het station en probeer de oplaadcyclus opnieuw te starten."),
        "pl": ("Przekroczony czas ładowania", "Cykl ładowania przekroczył dozwolony czas.", "Sprawdź styki stacji i spróbuj ponownie uruchomić cykl ładowania."),
        "pt": ("Tempo de carregamento esgotado", "O ciclo de carregamento excedeu o tempo limite.", "Verifique os contactos da base e tente reiniciar o ciclo de carregamento."),
    },
    120: {
        "de": ("Batterie nicht ladebereit", "Die Batterie meldet einen Fehler oder ist nicht bereit zum Laden.", "Batterie für 15 Minuten herausnehmen, wieder einsetzen und erneut laden."),
        "es": ("Batería no lista para cargar", "La batería indica un error o no está lista para cargar.", "Retire la batería durante 15 minutos, vuelva a colocarla y cargue de nuevo."),
        "fr": ("Batterie pas prête à charger", "La batterie signale une erreur ou n'est pas prête à être chargée.", "Retirez la batterie pendant 15 minutes, remettez-la en place et rechargez."),
        "it": ("Batteria non pronta per la ricarica", "La batteria segnala un errore o non è pronta per la ricarica.", "Rimuovere la batteria per 15 minuti, reinserirla e ricaricare."),
        "nl": ("Batterij niet klaar om te laden", "De batterij meldt een fout of is niet klaar om te laden.", "Haal de batterij 15 minuten uit de robot, plaats hem terug en laad opnieuw."),
        "pl": ("Akumulator niegotowy do ładowania", "Akumulator zgłasza błąd lub nie jest gotowy do ładowania.", "Wyjmij akumulator na 15 minut, włóż go ponownie i naładuj."),
        "pt": ("Bateria não pronta para carregar", "A bateria indica um erro ou não está pronta para carregar.", "Retire a bateria durante 15 minutos, volte a colocá-la e carregue novamente."),
    },
    121: {
        "de": ("In der Basis, lädt aber nicht", "Der Roboter steht auf der Basis, lädt aber nicht.", "Ladekontakte am Roboter und an der Basis reinigen."),
        "es": ("En la base pero sin cargar", "El robot está en su base pero no se carga.", "Limpie los contactos de carga del robot y de la base."),
        "fr": ("Sur la base mais ne charge pas", "Le robot est sur sa base mais ne charge pas.", "Nettoyez les contacts de charge du robot et de la base."),
        "it": ("Sulla base ma non in ricarica", "Il robot è sulla base ma non si ricarica.", "Pulire i contatti di ricarica del robot e della base."),
        "nl": ("In het basisstation maar laadt niet", "De robot staat in het basisstation maar laadt niet.", "Reinig de laadcontacten op de robot en op het basisstation."),
        "pl": ("Na stacji, ale się nie ładuje", "Robot stoi na stacji, ale się nie ładuje.", "Wyczyść styki ładowania na robocie i na stacji."),
        "pt": ("Na base mas sem carregar", "O robô está na base mas não está a carregar.", "Limpe os contactos de carregamento do robô e da base."),
    },
}

#: {lang: {code: {label, description, action}}}, the shape the lookup reads.
ERROR_CATALOGUE_TRANSLATIONS: Final[dict[str, dict[int, dict[str, str]]]] = {}
for _code, _by_lang in _TEXTS.items():
    for _lang, (_label, _description, _action) in _by_lang.items():
        ERROR_CATALOGUE_TRANSLATIONS.setdefault(_lang, {})[_code] = {
            "label": _label,
            "description": _description,
            "action": _action,
        }
