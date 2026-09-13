// Публичный граф клиники. Карточки пациентов сюда не кладём.
// МКБ: фрагмент для демо; полный классификатор — CSV → ingest.

CREATE CONSTRAINT doctor_id IF NOT EXISTS FOR (d:Doctor) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT service_id IF NOT EXISTS FOR (s:Service) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT branch_id IF NOT EXISTS FOR (b:Branch) REQUIRE b.id IS UNIQUE;
CREATE CONSTRAINT prep_id IF NOT EXISTS FOR (p:Preparation) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT icd_code IF NOT EXISTS FOR (c:IcdCode) REQUIRE c.code IS UNIQUE;

MERGE (les:Branch {id: 'lesnaya', name: 'Лесная', address: 'ул. Лесная, 12', acl: 'public'});
MERGE (yuz:Branch {id: 'yuzhny', name: 'Южный', address: 'пр. Мира, 45', acl: 'public'});

MERGE (sokolova:Doctor {id: 'doc-sokolova', name: 'Соколова Е.В.', specialty: 'терапевт', acl: 'public'});
MERGE (orlov:Doctor {id: 'doc-orlov', name: 'Орлов Д.И.', specialty: 'гастроэнтеролог', acl: 'public'});
MERGE (morozova:Doctor {id: 'doc-morozova', name: 'Морозова А.П.', specialty: 'УЗИ', acl: 'public'});
MERGE (kim:Doctor {id: 'doc-kim', name: 'Ким С.А.', specialty: 'кардиолог', acl: 'public'});
MERGE (belova:Doctor {id: 'doc-belova', name: 'Белова И.С.', specialty: 'педиатр', acl: 'public'});

MERGE (ter:Service {id: 'TER-01', name: 'Приём терапевта первичный', price: 2800, acl: 'public'});
MERGE (ped:Service {id: 'PED-01', name: 'Приём педиатра первичный', price: 2900, acl: 'public'});
MERGE (gas:Service {id: 'GAS-01', name: 'Приём гастроэнтеролога', price: 3400, acl: 'public'});
MERGE (car:Service {id: 'CAR-01', name: 'Приём кардиолога + ЭКГ', price: 3800, acl: 'public'});
MERGE (usi:Service {id: 'USI-01', name: 'УЗИ органов брюшной полости', price: 3200, acl: 'public'});
MERGE (usiK:Service {id: 'USI-02', name: 'УЗИ ОБП ребёнку', price: 3000, acl: 'public'});
MERGE (lab1:Service {id: 'LAB-01', name: 'Общий анализ крови', price: 650, acl: 'public'});
MERGE (lab2:Service {id: 'LAB-02', name: 'Биохимия крови', price: 1900, acl: 'public'});
MERGE (egd:Service {id: 'END-01', name: 'Гастроскопия', price: 7500, acl: 'public'});

MERGE (pUzi:Preparation {id: 'prep-uzi', title: 'Подготовка к УЗИ ОБП', hours_fasting: 6, acl: 'public'});
MERGE (pUziK:Preparation {id: 'prep-uzi-child', title: 'Подготовка к УЗИ ОБП ребёнку', hours_fasting: 5, acl: 'public'});
MERGE (pLab:Preparation {id: 'prep-blood', title: 'Подготовка к анализам крови', hours_fasting: 8, acl: 'public'});
MERGE (pEgd:Preparation {id: 'prep-egd', title: 'Подготовка к гастроскопии', hours_fasting: 8, acl: 'public'});

MERGE (k21:IcdCode {code: 'K21', name: 'Гастроэзофагеальный рефлюкс', acl: 'public'});
MERGE (k210:IcdCode {code: 'K21.0', name: 'Гастроэзофагеальный рефлюкс с эзофагитом', acl: 'public'});
MERGE (k25:IcdCode {code: 'K25', name: 'Язва желудка', acl: 'public'});
MERGE (k29:IcdCode {code: 'K29', name: 'Гастрит и дуоденит', acl: 'public'});
MERGE (k80:IcdCode {code: 'K80', name: 'Желчекаменная болезнь [холелитиаз]', acl: 'public'});
MERGE (k801:IcdCode {code: 'K80.1', name: 'Камни желчного пузыря с другим холециститом', acl: 'public'});
MERGE (n28:IcdCode {code: 'N28', name: 'Другие болезни почки и мочеточника', acl: 'public'});
MERGE (n281:IcdCode {code: 'N28.1', name: 'Киста почки, приобретенная', acl: 'public'});

MERGE (k210)-[:PARENT]->(k21);
MERGE (k801)-[:PARENT]->(k80);
MERGE (n281)-[:PARENT]->(n28);

MERGE (sokolova)-[:PROVIDES]->(ter);
MERGE (orlov)-[:PROVIDES]->(gas);
MERGE (orlov)-[:PROVIDES]->(egd);
MERGE (morozova)-[:PROVIDES]->(usi);
MERGE (morozova)-[:PROVIDES]->(usiK);
MERGE (kim)-[:PROVIDES]->(car);
MERGE (belova)-[:PROVIDES]->(ped);

MERGE (sokolova)-[:WORKS_AT]->(les);
MERGE (sokolova)-[:WORKS_AT]->(yuz);
MERGE (orlov)-[:WORKS_AT]->(les);
MERGE (morozova)-[:WORKS_AT]->(les);
MERGE (morozova)-[:WORKS_AT]->(yuz);
MERGE (kim)-[:WORKS_AT]->(yuz);
MERGE (belova)-[:WORKS_AT]->(les);

MERGE (ter)-[:AVAILABLE_AT]->(les);
MERGE (ter)-[:AVAILABLE_AT]->(yuz);
MERGE (ped)-[:AVAILABLE_AT]->(les);
MERGE (gas)-[:AVAILABLE_AT]->(les);
MERGE (car)-[:AVAILABLE_AT]->(yuz);
MERGE (usi)-[:AVAILABLE_AT]->(les);
MERGE (usi)-[:AVAILABLE_AT]->(yuz);
MERGE (usiK)-[:AVAILABLE_AT]->(les);
MERGE (lab1)-[:AVAILABLE_AT]->(les);
MERGE (lab1)-[:AVAILABLE_AT]->(yuz);
MERGE (lab2)-[:AVAILABLE_AT]->(les);
MERGE (lab2)-[:AVAILABLE_AT]->(yuz);
MERGE (egd)-[:AVAILABLE_AT]->(les);

MERGE (usi)-[:REQUIRES]->(pUzi);
MERGE (usiK)-[:REQUIRES]->(pUziK);
MERGE (lab1)-[:REQUIRES]->(pLab);
MERGE (lab2)-[:REQUIRES]->(pLab);
MERGE (egd)-[:REQUIRES]->(pEgd);

MERGE (egd)-[:INDICATED_FOR]->(k21);
MERGE (egd)-[:INDICATED_FOR]->(k25);
MERGE (egd)-[:INDICATED_FOR]->(k29);
MERGE (usi)-[:INDICATED_FOR]->(k80);
MERGE (usiK)-[:INDICATED_FOR]->(n28);
