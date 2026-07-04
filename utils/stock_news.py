import random

# News templates for the Stock Market
# Format: {symbol: [list of (message, price_multiplier)]}
# Multiplier > 1.0 positive, < 1.0 negative

MARKET_NEWS = {

    # ------------------------------------------------------------------ #
    # EMPRESAS ACTUALES DEL MERCADO                                       #
    # ------------------------------------------------------------------ #

    "VRTX": [
        ("Vertex Dynamics announces a breakthrough in Quantum AI processing!", 1.15),
        ("A major security breach was detected in Vertex's neural network servers.", 0.85),
        ("Vertex Dynamics signs a massive contract with the Global Defense Agency.", 1.10),
        ("The CEO of Vertex Dynamics was seen testing a secret exoskeleton prototype.", 1.05),
        ("Regulatory concerns over Vertex's AI ethics cause a slight market dip.", 0.92),
        ("Vertex's new robot companion 'V-Buddy' sells out in minutes!", 1.08),
        ("Rumors of a merger between Vertex and a major energy firm surface.", 1.04),
        ("A software glitch in Vertex's automated factories slows down production.", 0.90),
        ("Vertex Dynamics wins the 'Innovation of the Year' award.", 1.06),
        ("Vertex faces a lawsuit over data privacy in its latest AI model.", 0.88),
    ],
    "GLBL": [
        ("Global Energy successfully launches the world's largest solar farm.", 1.12),
        ("An oil spill in the northern sector causes environmental backlash for Global Energy.", 0.80),
        ("Global Energy discovers a massive lithium deposit in a remote region.", 1.15),
        ("Government subsidies for green energy boost Global Energy's outlook.", 1.07),
        ("A series of power outages in the city are blamed on Global Energy's grid.", 0.88),
        ("Global Energy's new fusion reactor prototype shows promising results.", 1.10),
        ("High maintenance costs for aging infrastructure impact Global Energy's profits.", 0.93),
        ("Global Energy partners with a tech giant to build smart cities.", 1.05),
        ("Global Energy's quarterly report shows record-breaking revenue.", 1.09),
        ("A sudden drop in global energy demand causes a minor stock decline.", 0.95),
    ],
    "AURA": [
        ("Aura Pharmaceuticals receives FDA approval for a revolutionary cancer treatment.", 1.20),
        ("Aura Pharmaceuticals faces a recall of its popular allergy medication.", 0.75),
        ("Aura's new longevity drug 'Aeterna' enters the final phase of testing.", 1.12),
        ("Rumors of Aura Pharmaceuticals being acquired by a tech giant drive prices up.", 1.08),
        ("Aura Pharmaceuticals' research lab suffers a catastrophic equipment failure.", 0.85),
        ("Aura Pharmaceuticals opens a new state-of-the-art research center in Europe.", 1.05),
        ("Aura Pharmaceuticals' patent for a key drug is challenged in court.", 0.88),
        ("Aura Pharmaceuticals' CEO announces a focus on affordable healthcare.", 1.03),
        ("Aura Pharmaceuticals' vaccine distribution network expands globally.", 1.06),
        ("Aura Pharmaceuticals' latest clinical trial yields disappointing results.", 0.82),
    ],
    "ORBT": [
        ("Orbital Space successfully lands the first commercial mission on Mars!", 1.25),
        ("An Orbital Space rocket explodes during a routine test flight.", 0.70),
        ("Orbital Space announces a new luxury space hotel 'The Celestial'.", 1.15),
        ("Orbital Space's satellite network 'Starlight' reaches full global coverage.", 1.10),
        ("Space debris damages an Orbital Space orbital platform.", 0.85),
        ("Orbital Space signs a multi-billion dollar deal for asteroid mining.", 1.18),
        ("A major investor pulls out of Orbital Space's moon colony project.", 0.80),
        ("Orbital Space's first space tourism flight is a resounding success.", 1.09),
        ("Orbital Space faces regulatory hurdles for its new orbital elevator.", 0.92),
        ("Orbital Space's deep space probe sends back incredible data from Europa.", 1.04),
    ],
    "TITN": [
        ("Titan Heavy Industries secures a contract for a new fleet of cargo ships.", 1.10),
        ("A strike at Titan's main manufacturing plant halts all production.", 0.82),
        ("Titan Heavy Industries unveils a new line of ultra-durable mining equipment.", 1.08),
        ("Titan's construction division wins a bid for a massive undersea bridge.", 1.07),
        ("Titan Heavy Industries faces allegations of using substandard materials.", 0.85),
        ("Titan Heavy Industries' new automated assembly line increases efficiency.", 1.06),
        ("Titan Heavy Industries' quarterly earnings fall short of expectations.", 0.90),
        ("Titan Heavy Industries' expansion into the Asian market is ahead of schedule.", 1.04),
        ("Titan Heavy Industries' CEO steps down unexpectedly, causing uncertainty.", 0.93),
        ("Titan Heavy Industries' new eco-friendly steel production is a hit.", 1.05),
    ],
    "CRPT": [
        ("CryptoVault Financial announces a new decentralized exchange platform.", 1.18),
        ("Regulators launch an investigation into CryptoVault's transaction practices.", 0.72),
        ("CryptoVault partners with a major bank for blockchain integration.", 1.14),
        ("A massive hack drains funds from CryptoVault's hot wallets.", 0.60),
        ("CryptoVault's new staking program offers record-high APY rewards.", 1.12),
        ("Government cracks down on crypto exchanges, hitting CryptoVault hard.", 0.78),
        ("CryptoVault launches its own stablecoin, shaking up the market.", 1.10),
        ("A prominent whale dumps a massive position in CryptoVault tokens.", 0.82),
        ("CryptoVault achieves record trading volume in Q3.", 1.08),
        ("Rumors of CryptoVault insolvency spark a brief panic sell-off.", 0.68),
    ],

    # ------------------------------------------------------------------ #
    # EMPRESAS IPO — POOL DE POSIBLES EMPRESAS                           #
    # ------------------------------------------------------------------ #

    # Tecnología
    "NOVA": [
        ("Nova Systems debuts its self-healing microchip, sending shares soaring.", 1.18),
        ("Nova Systems loses a key government contract to a rival bidder.", 0.80),
        ("Nova's neural interface headset gets cleared for consumer release.", 1.14),
        ("A patent war with a Silicon Valley giant puts Nova on the back foot.", 0.84),
        ("Nova Systems posts its best quarterly revenue since founding.", 1.10),
        ("A critical vulnerability is discovered in Nova's flagship software.", 0.78),
        ("Nova Systems acquires a promising AI startup for $2 billion.", 1.08),
        ("Supply shortages delay Nova's most-anticipated product launch.", 0.87),
        ("Nova Systems named 'Most Innovative Company' by a leading tech magazine.", 1.06),
        ("Nova Systems faces a class-action lawsuit over device overheating.", 0.82),
    ],
    "QNTM": [
        ("Quantum Leap Computing achieves stable 1000-qubit entanglement — a world first.", 1.22),
        ("A cooling system failure destroys Quantum Leap's main research lab.", 0.72),
        ("Quantum Leap secures a $5B defense contract for quantum encryption.", 1.20),
        ("A top researcher defects to a competitor, taking key IP with them.", 0.80),
        ("Quantum Leap's new quantum cloud service attracts 10,000 enterprise clients.", 1.12),
        ("Benchmark tests reveal Quantum Leap's processor underperforms claims.", 0.85),
        ("Quantum Leap announces a partnership with the world's largest bank.", 1.10),
        ("Export restrictions on quantum tech hit Quantum Leap's overseas sales.", 0.88),
        ("Quantum Leap wins the prestigious 'Global Tech Prize'.", 1.07),
        ("Quantum Leap's IPO lock-up expires — insider selling creates pressure.", 0.83),
    ],
    "NXUS": [
        ("Nexus Networks rolls out the world's first 7G infrastructure in 50 cities.", 1.16),
        ("A nationwide outage caused by Nexus Networks triggers customer fury.", 0.74),
        ("Nexus Networks wins a UN contract to connect rural regions worldwide.", 1.13),
        ("A cyberattack cripples Nexus Networks' core routing systems for 6 hours.", 0.76),
        ("Nexus Networks' satellite internet service goes live, rivaling major players.", 1.11),
        ("Regulators fine Nexus Networks $800M for anti-competitive pricing.", 0.83),
        ("Nexus Networks' new fiber deal covers 30 million households.", 1.08),
        ("Rising infrastructure costs squeeze Nexus Networks' margins.", 0.90),
        ("Nexus Networks reports a 40% jump in broadband subscriptions.", 1.09),
        ("A rival poaches Nexus Networks' entire cloud engineering team.", 0.81),
    ],
    "ZRTH": [
        ("Zeroth AI releases an LLM that outperforms all known benchmarks.", 1.20),
        ("Zeroth AI's chatbot goes viral for giving dangerous medical advice.", 0.68),
        ("Zeroth AI lands a $10B licensing deal with the world's largest tech firm.", 1.18),
        ("Regulators propose banning Zeroth AI's facial recognition product.", 0.79),
        ("Zeroth AI's autonomous driving software passes all safety certifications.", 1.15),
        ("A whistleblower claims Zeroth AI trained its model on stolen data.", 0.72),
        ("Zeroth AI opens its API, attracting one million developers overnight.", 1.10),
        ("Zeroth AI burns through cash reserves faster than expected.", 0.84),
        ("Zeroth AI named a 'Top 10 Company to Watch' by Fortune.", 1.07),
        ("Zeroth AI's key patent is ruled invalid by an appeals court.", 0.80),
    ],

    # Energía & Sostenibilidad
    "SOLX": [
        ("SolarX unveils a solar panel with 52% efficiency — shattering the record.", 1.20),
        ("A massive hurricane destroys SolarX's largest production facility.", 0.70),
        ("SolarX wins a government contract to power an entire country with solar.", 1.18),
        ("Falling silicon prices crush SolarX's profit margins.", 0.85),
        ("SolarX's floating solar farm in the Pacific goes fully operational.", 1.12),
        ("A fire at SolarX's storage plant causes billions in damage.", 0.73),
        ("SolarX partners with a car giant to install solar rooftops on new homes.", 1.09),
        ("SolarX faces backlash over land use in protected ecological zones.", 0.87),
        ("SolarX's Q2 installations break the company's all-time record.", 1.10),
        ("A rival files an IP lawsuit, claiming SolarX stole solar cell tech.", 0.82),
    ],
    "HYDR": [
        ("HydroGen Power opens the world's largest green hydrogen plant.", 1.17),
        ("An explosion at HydroGen's refueling station kills three workers.", 0.65),
        ("HydroGen Power secures a deal to supply hydrogen to all EU freight routes.", 1.15),
        ("A transportation accident spills HydroGen fuel into a local river.", 0.75),
        ("HydroGen Power's new electrolysis tech cuts production costs by 40%.", 1.13),
        ("Rising electricity prices make HydroGen production uneconomical.", 0.84),
        ("HydroGen Power announces a joint venture with a major shipping company.", 1.09),
        ("Safety regulators suspend HydroGen's newest plant after an inspection.", 0.80),
        ("HydroGen Power's stock jumps on record quarterly deliveries.", 1.11),
        ("A key HydroGen executive is arrested on fraud charges.", 0.71),
    ],
    "CARB": [
        ("CarbonZero captures a record 1 million tons of CO₂ in a single month.", 1.14),
        ("Carbon markets crash 30%, devastating CarbonZero's core revenue stream.", 0.72),
        ("CarbonZero signs the largest carbon credit deal in history with a major airline.", 1.16),
        ("An audit reveals CarbonZero inflated its carbon capture figures.", 0.60),
        ("CarbonZero's direct-air-capture tech is certified by the UN.", 1.12),
        ("Heavy rains flood CarbonZero's main sequestration site.", 0.83),
        ("CarbonZero partners with 50 governments on a new emissions treaty.", 1.10),
        ("Rising operating costs put CarbonZero's profitability in question.", 0.87),
        ("CarbonZero wins the 'Global Climate Impact Award'.", 1.06),
        ("A class-action lawsuit accuses CarbonZero of greenwashing.", 0.76),
    ],

    # Finanzas & Banca
    "BRVK": [
        ("BraveBank launches an AI financial advisor used by 5 million customers instantly.", 1.13),
        ("BraveBank suffers a data breach exposing 20 million customer records.", 0.68),
        ("BraveBank expands into 15 new countries, doubling its user base.", 1.15),
        ("Regulators freeze BraveBank assets pending a money-laundering probe.", 0.62),
        ("BraveBank's zero-fee model attracts 2 million new users this quarter.", 1.10),
        ("Rising loan defaults hit BraveBank's balance sheet hard.", 0.80),
        ("BraveBank is acquired by a global financial giant in a surprise deal.", 1.20),
        ("BraveBank's app outage lasts 18 hours, sparking user exodus.", 0.77),
        ("BraveBank's IPO is the most-subscribed in its sector this decade.", 1.12),
        ("BraveBank faces a $1.2B fine for violating consumer protection laws.", 0.73),
    ],
    "PYDE": [
        ("PyDex Exchange surpasses 100 million daily transactions.", 1.14),
        ("PyDex suffers a $400M exploit due to a smart contract bug.", 0.55),
        ("PyDex introduces the first fully regulated DeFi lending market.", 1.16),
        ("PyDex's governance token crashes after a contentious protocol vote.", 0.74),
        ("PyDex partners with a central bank to pilot a CBDC.", 1.18),
        ("A major country bans PyDex, cutting off 15% of its volume.", 0.78),
        ("PyDex's staking yields attract $8B in new liquidity.", 1.12),
        ("PyDex's insurance fund is wiped out after a market flash crash.", 0.70),
        ("PyDex named 'Best DeFi Platform' at the Global Blockchain Summit.", 1.08),
        ("PyDex faces a class-action over undisclosed conflicts of interest.", 0.76),
    ],

    # Salud & Biotech
    "GNTX": [
        ("Genetix Corp announces a gene therapy that cures a previously fatal condition.", 1.25),
        ("Genetix Corp's lead drug candidate fails Phase 3 trials.", 0.62),
        ("Genetix Corp partners with a major hospital chain for genome sequencing.", 1.13),
        ("A regulatory agency rejects Genetix Corp's manufacturing practices.", 0.78),
        ("Genetix Corp's CRISPR patent is upheld, blocking all competitors.", 1.17),
        ("Genetix Corp's CEO resigns amid a personal scandal.", 0.80),
        ("Genetix Corp receives a $3B grant from a global health foundation.", 1.15),
        ("A clinical trial is halted after adverse reactions in patients.", 0.68),
        ("Genetix Corp posts its first profitable quarter since founding.", 1.10),
        ("Genetix Corp faces backlash over its pricing of a life-saving drug.", 0.82),
    ],
    "MNDR": [
        ("MindRise reveals a non-invasive brain implant that restores full mobility.", 1.22),
        ("MindRise's clinical trial is suspended after two participants suffer seizures.", 0.65),
        ("MindRise signs a deal with the world's largest military for neuro-enhancement tech.", 1.16),
        ("A data privacy scandal erupts over MindRise collecting brainwave data.", 0.72),
        ("MindRise's depression treatment is approved for mass prescription.", 1.18),
        ("MindRise's key scientist leaves to found a competing startup.", 0.83),
        ("MindRise raises $2B in its latest funding round at record valuation.", 1.12),
        ("Animal rights groups protest MindRise's testing methods, damaging its brand.", 0.79),
        ("MindRise wins the Nobel Prize in Medicine for its neural interface research.", 1.20),
        ("MindRise's flagship product is recalled due to a manufacturing defect.", 0.70),
    ],

    # Transporte & Logística
    "DRFT": [
        ("Drift Motors reveals a hypercar that goes from 0–300 km/h in 1.8 seconds.", 1.14),
        ("A Drift Motors vehicle catches fire on a highway, injuring passengers.", 0.72),
        ("Drift Motors announces full self-driving across all models by year end.", 1.12),
        ("Drift Motors' battery recall affects 80,000 vehicles.", 0.75),
        ("Drift Motors opens its 500th Supercharger station worldwide.", 1.08),
        ("A global chip shortage halts Drift Motors production for six weeks.", 0.83),
        ("Drift Motors' trucks secure a $4B contract with a major logistics firm.", 1.11),
        ("Drift Motors misses its delivery targets for the third consecutive quarter.", 0.80),
        ("Drift Motors' CEO unveils a flying car prototype — social media goes wild.", 1.09),
        ("Drift Motors faces a safety investigation over autopilot-related accidents.", 0.78),
    ],
    "SKYW": [
        ("SkyWay Airlines reports its highest-ever passenger load factor.", 1.12),
        ("A SkyWay Airlines plane makes an emergency landing after engine failure.", 0.70),
        ("SkyWay Airlines launches the first non-stop flight between two remote continents.", 1.10),
        ("Fuel prices spike 30%, devastating SkyWay Airlines' cost structure.", 0.77),
        ("SkyWay Airlines unveils a hydrogen-powered aircraft for 2027.", 1.13),
        ("A pilot strike grounds 40% of SkyWay Airlines' fleet.", 0.74),
        ("SkyWay Airlines acquires a regional carrier, expanding its network by 25%.", 1.09),
        ("SkyWay Airlines faces a lawsuit over a mass cancellation event.", 0.80),
        ("SkyWay Airlines wins 'Best Airline in the World' for the fifth time.", 1.07),
        ("A new carbon tax on aviation hits SkyWay Airlines' margins hard.", 0.85),
    ],
    "XPRS": [
        ("Xpress Logistics delivers its billionth package using fully autonomous drones.", 1.14),
        ("A warehouse fire destroys Xpress Logistics' largest distribution hub.", 0.68),
        ("Xpress Logistics wins a last-mile contract with the world's biggest retailer.", 1.16),
        ("Xpress Logistics' drone fleet is grounded by regulators over airspace violations.", 0.78),
        ("Xpress Logistics' new 30-minute delivery service expands to 200 cities.", 1.12),
        ("A cyberattack locks Xpress Logistics out of its routing systems for 12 hours.", 0.76),
        ("Xpress Logistics partners with a robotics firm for fully automated warehouses.", 1.10),
        ("Harsh winter conditions halt Xpress Logistics' operations in the northern region.", 0.83),
        ("Xpress Logistics' Q3 profit triples, beating all analyst forecasts.", 1.13),
        ("A labor union dispute at Xpress Logistics threatens the holiday shipping season.", 0.79),
    ],

    # Entretenimiento & Gaming
    "VRTL": [
        ("VirtualWorld launches a VR metaverse with 10 million concurrent users on day one.", 1.18),
        ("VirtualWorld's flagship game is hit by a massive cheating scandal.", 0.76),
        ("VirtualWorld acquires the most popular mobile gaming studio for $8B.", 1.15),
        ("VirtualWorld's platform crashes during its biggest live event.", 0.73),
        ("VirtualWorld's new VR headset breaks pre-order records.", 1.12),
        ("A data breach exposes the personal data of 50 million VirtualWorld users.", 0.70),
        ("VirtualWorld's esports league secures a $500M broadcasting deal.", 1.10),
        ("VirtualWorld faces a loot box ban in several major markets.", 0.80),
        ("VirtualWorld's new open-world RPG becomes the fastest-selling game ever.", 1.16),
        ("A child safety controversy forces VirtualWorld to shut down a major game mode.", 0.75),
    ],
    "PLSR": [
        ("Pulsar Entertainment's summer blockbuster breaks the global box office record.", 1.15),
        ("A Pulsar Entertainment film is pulled from release after a star's scandal.", 0.74),
        ("Pulsar Entertainment's streaming platform hits 200 million subscribers.", 1.13),
        ("Pulsar Entertainment loses the rights to its most beloved franchise.", 0.80),
        ("Pulsar Entertainment's AI-generated film scores 8 Oscar nominations.", 1.12),
        ("Pulsar Entertainment's theme park expansion is delayed by two years.", 0.84),
        ("Pulsar Entertainment acquires a legendary music label for $5B.", 1.10),
        ("Pulsar Entertainment's ad revenue crashes amid a global recession.", 0.78),
        ("Pulsar Entertainment's new immersive concert experience sells out in seconds.", 1.09),
        ("A massive piracy leak of Pulsar Entertainment's unreleased content goes viral.", 0.76),
    ],

    # Alimentación & Consumo
    "NUTX": [
        ("NutriX unveils lab-grown meat indistinguishable from beef — demand explodes.", 1.16),
        ("NutriX faces a contamination scare that triggers a global product recall.", 0.65),
        ("NutriX lands a deal to supply its protein products to 50,000 restaurants.", 1.13),
        ("A documentary exposes controversial practices at NutriX's production plants.", 0.72),
        ("NutriX's personalized nutrition app reaches 20 million paying subscribers.", 1.10),
        ("A key NutriX ingredient is banned by the FDA pending safety review.", 0.78),
        ("NutriX's zero-sugar line becomes the fastest-growing product in history.", 1.12),
        ("NutriX's supply chain is disrupted by extreme weather in key growing regions.", 0.83),
        ("NutriX wins the 'World Food Innovation Award'.", 1.07),
        ("Rising raw material costs force NutriX to slash its profit guidance.", 0.82),
    ],

    # Defensa & Seguridad
    "ARMX": [
        ("ArmX Defense unveils an autonomous combat drone with unmatched precision.", 1.18),
        ("ArmX Defense loses a $20B government contract to a surprise competitor.", 0.70),
        ("ArmX Defense partners with NATO for next-generation cyber warfare systems.", 1.16),
        ("An ArmX Defense weapons system malfunctions during a public demonstration.", 0.75),
        ("ArmX Defense's new missile defense shield is approved for deployment.", 1.14),
        ("International sanctions target ArmX Defense over sales to a banned country.", 0.68),
        ("ArmX Defense's Q2 orders surge amid rising global tensions.", 1.12),
        ("A whistleblower leaks details of ArmX Defense's secret surveillance project.", 0.78),
        ("ArmX Defense wins 'Defense Contractor of the Year'.", 1.07),
        ("An explosion at ArmX Defense's testing facility injures 12 engineers.", 0.72),
    ],

    # Inmobiliario & Construcción
    "BRKR": [
        ("BrickRock Properties announces a record-breaking luxury development in Dubai.", 1.14),
        ("A BrickRock Properties skyscraper is evacuated over structural concerns.", 0.73),
        ("BrickRock Properties acquires prime real estate in 10 major capitals.", 1.12),
        ("A market correction in housing wipes out 15% of BrickRock's portfolio value.", 0.79),
        ("BrickRock Properties' smart home community sells out in 48 hours.", 1.10),
        ("Flooding devastates three BrickRock Properties residential developments.", 0.76),
        ("BrickRock Properties launches an affordable housing fund, praised globally.", 1.08),
        ("Rising interest rates reduce demand for BrickRock's premium properties.", 0.84),
        ("BrickRock Properties wins 'Best Real Estate Developer of the Year'.", 1.06),
        ("A corruption scandal links BrickRock Properties to illegal planning permits.", 0.70),
    ],

    # Noticias Generales del Mercado
    "GENERAL": [
        ("The Global Stock Market enters a period of unprecedented growth!", 1.05),
        ("A sudden economic recession causes a market-wide decline.", 0.95),
        ("New trade agreements boost investor confidence across all sectors.", 1.03),
        ("A global logistics crisis slows down international trade.", 0.97),
        ("Technological advancements drive a minor boom in the tech sector.", 1.02),
        ("Political instability in key regions causes market volatility.", 0.98),
        ("Interest rates are lowered, encouraging more investment.", 1.04),
        ("A major bank failure sends shockwaves through the financial world.", 0.92),
        ("Record-low unemployment rates boost consumer spending.", 1.03),
        ("A global pandemic scare causes a temporary market panic.", 0.90),
        ("Inflation data comes in lower than expected, calming the markets.", 1.04),
        ("A geopolitical crisis in a key oil-producing region rattles investors.", 0.93),
        ("Central banks signal no rate hikes for the next year — markets cheer.", 1.05),
        ("A surprise election result in a major economy spooks global markets.", 0.94),
        ("A wave of retail investor buying pushes the market to new highs.", 1.06),
    ],
}

# Generic templates for any company NOT in MARKET_NEWS. {name} is replaced.
GENERIC_IPO_NEWS = [
    ("{name} reports stronger-than-expected quarterly earnings.", 1.12),
    ("{name}'s CEO makes a controversial statement, unsettling investors.", 0.88),
    ("{name} announces a major strategic partnership.", 1.10),
    ("{name} faces an unexpected supply chain disruption.", 0.85),
    ("{name} launches a new product line to overwhelmingly positive reviews.", 1.08),
    ("{name} is placed under regulatory scrutiny over compliance issues.", 0.82),
    ("Analysts upgrade {name} to 'Strong Buy' following recent results.", 1.14),
    ("{name} suffers a data breach affecting thousands of customers.", 0.78),
    ("{name} announces a share buyback program, boosting investor confidence.", 1.06),
    ("{name}'s expansion into new markets significantly exceeds expectations.", 1.11),
    ("{name} cuts its full-year guidance, disappointing the market.", 0.80),
    ("{name}'s founder steps down as CEO — shares react nervously.", 0.84),
    ("{name} secures a landmark government contract.", 1.15),
    ("{name} is named in a class-action lawsuit by former employees.", 0.79),
    ("{name} posts record revenue, smashing analyst estimates.", 1.13),
]


def get_random_news(active_symbols=None):
    """
    Get a random news event.
    - 70 %: company-specific news for symbols with dedicated MARKET_NEWS entries
    - 15 %: generic news applied to an IPO / unknown symbol
    - 15 %: general market-wide news (ALL)
    """
    from config import STOCKS

    current_symbols = active_symbols or list(STOCKS.keys())
    known_symbols   = [s for s in current_symbols if s in MARKET_NEWS]
    unknown_symbols = [s for s in current_symbols if s not in MARKET_NEWS]

    roll = random.random()

    if roll < 0.70 and known_symbols:
        symbol    = random.choice(known_symbols)
        news_item = random.choice(MARKET_NEWS[symbol])
        return symbol, news_item[0], news_item[1]

    elif roll < 0.85 and unknown_symbols:
        symbol       = random.choice(unknown_symbols)
        company_name = STOCKS.get(symbol, {}).get("name", symbol)
        template, multiplier = random.choice(GENERIC_IPO_NEWS)
        message = template.format(name=company_name)
        return symbol, message, multiplier

    else:
        news_item = random.choice(MARKET_NEWS["GENERAL"])
        return "ALL", news_item[0], news_item[1]
