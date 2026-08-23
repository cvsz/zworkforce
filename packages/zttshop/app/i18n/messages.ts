import type { Locale } from "./config";

type HomeCard = {
  index: string;
  status: string;
  icon: "shield" | "stack" | "route";
  title: string;
  body: string;
  code: string;
};

type HomeResource = {
  index: string;
  name: string;
  detail: string;
};

type LegalSection = {
  id: string;
  number: string;
  title: string;
  body: string;
  link?: {
    href: string;
    label: string;
    suffix: string;
  };
};

export type HomeCopy = {
  meta: {
    title: string;
    description: string;
  };
  nav: {
    capabilities: string;
    workflow: string;
    coverage: string;
    source: string;
    startBuilding: string;
    openMenu: string;
    language: string;
  };
  hero: {
    eyebrow: string;
    titleBefore: string;
    titleAccent: string;
    lead: string;
    primary: string;
    secondary: string;
    installLabel: string;
    notes: string[];
    monitor: {
      title: string;
      live: string;
      label: string;
      statement: string;
      chip: string;
      path: string;
      resource: string;
      signed: string;
      status: string;
      responseTime: string;
      stats: Array<{ label: string; value: string }>;
      footer: string;
      requestLabel: string;
      responseLabel: string;
    };
  };
  proof: Array<{ value: string; label: string }>;
  capabilities: {
    kicker: string;
    title: string;
    intro: string;
    cards: HomeCard[];
  };
  workflow: {
    kicker: string;
    title: string;
    intro: string;
    steps: Array<{ number: string; label: string; title: string; detail: string }>;
    fileName: string;
    language: string;
    footer: string;
  };
  coverage: {
    kicker: string;
    title: string;
    intro: string;
    resources: HomeResource[];
    ribbon: Array<{ title: string; detail: string }>;
  };
  cta: {
    kicker: string;
    title: string;
    body: string;
    github: string;
    terms: string;
  };
  footer: {
    description: string;
    setup: string;
    source: string;
    privacy: string;
    terms: string;
  };
};

export type LegalCopy = {
  meta: {
    title: string;
    description: string;
  };
  kicker: string;
  title: string;
  intro: string;
  effective: string;
  indexLabel: string;
  backToHome: string;
  sections: LegalSection[];
};

export type Dictionary = {
  site: {
    name: string;
    descriptor: string;
    meta: {
      title: string;
      description: string;
    };
  };
  common: {
    github: string;
    home: string;
    privacy: string;
    terms: string;
    source: string;
    setup: string;
    language: string;
    skipToContent: string;
    languageNames: Record<Locale, string>;
  };
  home: HomeCopy;
  privacy: LegalCopy;
  terms: LegalCopy;
};

const en: Dictionary = {
  site: {
    name: "zTTShop",
    descriptor: "PHP SDK",
    meta: {
      title: "zTTShop — TikTok Shop API Client for PHP",
      description: "A resource-first PHP SDK for building TikTok Shop integrations with a clear, consistent request layer.",
    },
  },
  common: {
    github: "GitHub",
    home: "Home",
    privacy: "Privacy",
    terms: "Terms",
    source: "Source",
    setup: "Setup",
    language: "Language",
    skipToContent: "Skip to content",
    languageNames: { en: "English", th: "ไทย" },
  },
  home: {
    meta: {
      title: "zTTShop — TikTok Shop API Client for PHP",
      description: "A resource-first PHP SDK for building TikTok Shop integrations with a clear, consistent request layer.",
    },
    nav: {
      capabilities: "Capabilities",
      workflow: "Workflow",
      coverage: "Coverage",
      source: "Source",
      startBuilding: "Start building",
      openMenu: "Open navigation",
      language: "Language",
    },
    hero: {
      eyebrow: "Open platform / PHP 8.1+",
      titleBefore: "Commerce APIs,",
      titleAccent: "without the fog.",
      lead: "zTTShop is a resource-first PHP client for TikTok Shop integrations. One readable request shape from authorization to fulfillment.",
      primary: "Get the quick start",
      secondary: "View source",
      installLabel: "Composer",
      notes: ["Signed requests", "Server-side tokens", "MIT licensed"],
      monitor: {
        title: "One client. Clear boundaries.",
        live: "live",
        label: "REQUEST PATH",
        statement: "One client. Clear boundaries.",
        chip: "REST / JSON",
        path: "/authorization/202309/shops",
        resource: "General resource",
        signed: "signed",
        status: "200 OK",
        responseTime: "842 ms",
        stats: [
          { label: "shops", value: "04" },
          { label: "region", value: "GLOBAL" },
          { label: "token", value: "SAFE" },
        ],
        footer: "Authorization to fulfillment in the same mental model.",
        requestLabel: "REQUEST",
        responseLabel: "RESPONSE",
      },
    },
    proof: [
      { value: "10", label: "Resource clients" },
      { value: "03", label: "API base URLs" },
      { value: "8.1+", label: "PHP runtime" },
      { value: "MIT", label: "Open-source license" },
    ],
    capabilities: {
      kicker: "Capabilities",
      title: "The shortest path from platform complexity to a useful call.",
      intro: "The SDK keeps the seams visible. Every capability has a home, every request has a predictable shape, and your application stays in control of the credentials.",
      cards: [
        {
          index: "A",
          status: "CORE",
          icon: "shield",
          title: "Auth that stays out of the way.",
          body: "Configure app keys, secrets, and access tokens once. Keep the sensitive layer on your server.",
          code: "TiktokShopConfig",
        },
        {
          index: "B",
          status: "RESOURCE-FIRST",
          icon: "stack",
          title: "Each API surface has a place.",
          body: "Authorization, products, orders, logistics, and finance map to readable resource clients.",
          code: "Resource\\General",
        },
        {
          index: "C",
          status: "PRODUCTION",
          icon: "route",
          title: "Built for the next real request.",
          body: "Modern PHP support, multiple API hosts, tests, and a small surface you can reason about.",
          code: "httpCallGet()",
        },
      ],
    },
    workflow: {
      kicker: "Workflow",
      title: "One SDK shape. Every operation where you expect it.",
      intro: "Follow the same three moves for every integration. The code preview is deliberately close to the story so the page teaches the product instead of only describing it.",
      steps: [
        { number: "01", label: "INPUT", title: "Install the client", detail: "Add one Composer package to the PHP application you already run." },
        { number: "02", label: "SIGN", title: "Keep credentials server-side", detail: "Set app keys, secrets, and tokens once. The request layer handles the rest." },
        { number: "03", label: "SHIP", title: "Call the resource you need", detail: "Move from authorization to orders, logistics, finance, or any supported surface." },
      ],
      fileName: "quick-start.php",
      language: "PHP",
      footer: "Credentials stay server-side by default.",
    },
    coverage: {
      kicker: "Resource coverage",
      title: "Meet the full commerce surface without a wall of documentation.",
      intro: "Start with the resource your application needs today. The same naming rhythm keeps the next integration familiar tomorrow.",
      resources: [
        { index: "01", name: "Authorization", detail: "OAuth, shops, tokens, and secure app entry." },
        { index: "02", name: "Products", detail: "Catalog, inventory, and listing operations." },
        { index: "03", name: "Orders", detail: "Order retrieval and fulfillment workflows." },
        { index: "04", name: "Logistics", detail: "Shipping providers, tracking, and labels." },
        { index: "05", name: "Finance", detail: "Statements, settlements, and transactions." },
        { index: "06", name: "Returns", detail: "Returns, refunds, and reverse logistics." },
        { index: "07", name: "Warehouse", detail: "Warehouse and stock management." },
        { index: "08", name: "Video", detail: "Video and content operations." },
        { index: "09", name: "Global", detail: "Cross-market platform operations." },
      ],
      ribbon: [
        { title: "AUTH", detail: "credentials" },
        { title: "REQUEST", detail: "resource client" },
        { title: "RESPONSE", detail: "your application" },
      ],
    },
    cta: {
      kicker: "Ready to ship",
      title: "Give your commerce layer a clearer center.",
      body: "Install the package, add your credentials, and make the first resource call today.",
      github: "Open on GitHub",
      terms: "Read terms",
    },
    footer: {
      description: "Unofficial PHP SDK for the TikTok Shop Open Platform.",
      setup: "Setup",
      source: "Source",
      privacy: "Privacy",
      terms: "Terms",
    },
  },
  privacy: {
    meta: { title: "Privacy Policy — zTTShop", description: "Privacy policy for the zTTShop PHP SDK website." },
    kicker: "LEGAL · PRIVACY",
    title: "Privacy Policy",
    intro: "How information is handled when you visit the zTTShop website or use the open-source PHP SDK.",
    effective: "Effective August 2, 2026",
    indexLabel: "On this page",
    backToHome: "Back to home",
    sections: [
      { id: "overview", number: "01", title: "Overview", body: "zTTShop is an unofficial, open-source PHP SDK for integrating with the TikTok Shop Open Platform. This website provides product information, installation guidance, and links to the project source. It is not operated by, affiliated with, or endorsed by TikTok." },
      { id: "information", number: "02", title: "Information we process", body: "This website does not ask you to create an account and does not collect TikTok Shop credentials, API keys, access tokens, payment details, or customer order data. Hosting infrastructure may automatically process limited technical information such as IP address, browser and device type, requested pages, timestamps, and security logs." },
      { id: "use", number: "03", title: "How information is used", body: "Technical information may be used to operate the website, maintain availability, diagnose errors, prevent abuse, and understand aggregate usage. We do not sell personal information or use this site to build advertising profiles." },
      { id: "sharing", number: "04", title: "Service providers and external links", body: "Infrastructure providers may process technical data solely to host, secure, and deliver the site. Links to GitHub, Composer/Packagist, TikTok, or other third-party services are governed by their own privacy policies." },
      { id: "security", number: "05", title: "SDK security", body: "Keep app secrets and tokens in server-side environment variables. Never commit credentials to source control or expose them to browsers. You are responsible for access controls, retention rules, and safeguards in applications built with the SDK." },
      { id: "rights", number: "06", title: "Retention and your rights", body: "Operational logs are retained only as reasonably necessary for security and service operation. Depending on your location, you may have rights to request access, correction, deletion, restriction, or objection regarding personal information." },
      { id: "changes", number: "07", title: "Changes to this policy", body: "We may update this policy as the website, hosting, or legal requirements change. The effective date above identifies the current version." },
      { id: "contact", number: "08", title: "Contact", body: "For privacy questions, open an issue in the", link: { href: "https://github.com/cvsz/zttshop-php/issues", label: "zTTShop GitHub repository", suffix: " Do not include credentials, tokens, customer data, or sensitive information in a public issue." } },
    ],
  },
  terms: {
    meta: { title: "Terms of Use — zTTShop", description: "Terms governing use of the zTTShop website and PHP SDK." },
    kicker: "LEGAL · TERMS",
    title: "Terms of Use",
    intro: "Terms for accessing this website and using the zTTShop open-source PHP SDK.",
    effective: "Effective August 2, 2026",
    indexLabel: "On this page",
    backToHome: "Back to home",
    sections: [
      { id: "acceptance", number: "01", title: "Acceptance", body: "By accessing this website or using the zTTShop SDK, you agree to these terms. If you do not agree, do not use the website or software. You must have legal capacity to accept these terms and authority to act for any organization whose systems you integrate." },
      { id: "license", number: "02", title: "Open-source license", body: "The SDK source code is made available under the MIT License. Your rights to use, copy, modify, merge, publish, distribute, sublicense, or sell copies are governed by that license and its copyright notice." },
      { id: "platform", number: "03", title: "TikTok Shop platform rules", body: "zTTShop is unofficial and is not affiliated with or endorsed by TikTok. Your application and API usage must comply with TikTok Shop Open Platform agreements, developer policies, rate limits, applicable commerce rules, and relevant laws." },
      { id: "credentials", number: "04", title: "Your systems and credentials", body: "You are responsible for app approval, credentials, token lifecycle, requested scopes, shop authorization, data accuracy, and actions taken through your integration. Protect secrets, apply least privilege, validate webhooks, and revoke compromised credentials." },
      { id: "conduct", number: "05", title: "Acceptable use", body: "You may not use the website or SDK to violate law, platform policies, privacy or intellectual property rights, distribute malware, gain unauthorized access, misrepresent transactions, or interfere with other services." },
      { id: "disclaimer", number: "06", title: "No warranty", body: "The website and SDK are provided “as is” and “as available,” without warranties of any kind. We do not warrant uninterrupted availability, compatibility with every API version, error-free operation, or fitness for a particular commercial purpose." },
      { id: "liability", number: "07", title: "Limitation of liability", body: "To the fullest extent permitted by law, project contributors will not be liable for indirect, incidental, special, consequential, exemplary, or punitive damages, or for lost profits, data, revenue, goodwill, orders, or business opportunities." },
      { id: "changes", number: "08", title: "Changes and availability", body: "We may revise the website, documentation, SDK, or these terms at any time. Continued use after an updated effective date constitutes acceptance of the revised terms." },
      { id: "contact", number: "09", title: "Contact", body: "For support or terms-related questions, use the", link: { href: "https://github.com/cvsz/zttshop-php/issues", label: "GitHub issue tracker", suffix: " Never post credentials, personal data, or confidential commerce information publicly." } },
    ],
  },
};

const th: Dictionary = {
  site: {
    name: "zTTShop",
    descriptor: "PHP SDK",
    meta: {
      title: "zTTShop — PHP SDK สำหรับ TikTok Shop API",
      description: "PHP SDK แบบ resource-first สำหรับสร้าง integration กับ TikTok Shop ด้วย request layer ที่ชัดเจนและสม่ำเสมอ",
    },
  },
  common: {
    github: "GitHub",
    home: "หน้าแรก",
    privacy: "ความเป็นส่วนตัว",
    terms: "ข้อกำหนด",
    source: "ซอร์สโค้ด",
    setup: "เริ่มต้นใช้งาน",
    language: "ภาษา",
    skipToContent: "ข้ามไปยังเนื้อหา",
    languageNames: { en: "English", th: "ไทย" },
  },
  home: {
    meta: {
      title: "zTTShop — PHP SDK สำหรับ TikTok Shop API",
      description: "PHP SDK แบบ resource-first สำหรับสร้าง integration กับ TikTok Shop ด้วย request layer ที่ชัดเจนและสม่ำเสมอ",
    },
    nav: {
      capabilities: "ความสามารถ",
      workflow: "ขั้นตอนทำงาน",
      coverage: "ขอบเขต API",
      source: "ซอร์สโค้ด",
      startBuilding: "เริ่มสร้างระบบ",
      openMenu: "เปิดเมนูนำทาง",
      language: "ภาษา",
    },
    hero: {
      eyebrow: "Open platform / PHP 8.1+",
      titleBefore: "Commerce APIs,",
      titleAccent: "ชัดเจนตั้งแต่ต้น.",
      lead: "zTTShop คือ PHP client แบบ resource-first สำหรับเชื่อมต่อ TikTok Shop ใช้รูปแบบ request เดียวที่อ่านง่าย ตั้งแต่ authorization ไปจนถึง fulfillment",
      primary: "ดู quick start",
      secondary: "ดูซอร์สโค้ด",
      installLabel: "Composer",
      notes: ["เซ็น request ให้แล้ว", "เก็บ token ฝั่ง server", "ใช้ไลเซนส์ MIT"],
      monitor: {
        title: "หนึ่ง client แบ่งขอบเขตชัดเจน",
        live: "ทำงานอยู่",
        label: "เส้นทาง REQUEST",
        statement: "หนึ่ง client แบ่งขอบเขตชัดเจน",
        chip: "REST / JSON",
        path: "/authorization/202309/shops",
        resource: "General resource",
        signed: "เซ็นแล้ว",
        status: "200 OK",
        responseTime: "842 ms",
        stats: [
          { label: "shops", value: "04" },
          { label: "region", value: "GLOBAL" },
          { label: "token", value: "SAFE" },
        ],
        footer: "จาก authorization ถึง fulfillment ด้วย mental model เดียวกัน",
        requestLabel: "REQUEST",
        responseLabel: "RESPONSE",
      },
    },
    proof: [
      { value: "10", label: "resource clients" },
      { value: "03", label: "API base URLs" },
      { value: "8.1+", label: "PHP runtime" },
      { value: "MIT", label: "โอเพนซอร์สไลเซนส์" },
    ],
    capabilities: {
      kicker: "ความสามารถ",
      title: "ลดระยะทางจากความซับซ้อนของ platform ไปสู่ call ที่ใช้งานได้จริง",
      intro: "SDK แบ่งขอบเขตให้เห็นชัด ทุก capability มีที่อยู่ ทุก request มีรูปแบบคาดเดาได้ และแอปของคุณยังควบคุม credentials เอง",
      cards: [
        { index: "A", status: "CORE", icon: "shield", title: "Auth ที่ไม่ขวางทางคุณ", body: "ตั้งค่า app keys, secrets และ access tokens ครั้งเดียว เก็บชั้นข้อมูลสำคัญไว้บน server", code: "TiktokShopConfig" },
        { index: "B", status: "RESOURCE-FIRST", icon: "stack", title: "ทุก API surface มีที่ของตัวเอง", body: "Authorization, products, orders, logistics และ finance ถูกจัดเป็น resource client ที่อ่านง่าย", code: "Resource\\General" },
        { index: "C", status: "PRODUCTION", icon: "route", title: "พร้อมสำหรับ request ถัดไป", body: "รองรับ PHP รุ่นใหม่ หลาย API hosts มี test และมี surface ที่ทีมเข้าใจได้ง่าย", code: "httpCallGet()" },
      ],
    },
    workflow: {
      kicker: "ขั้นตอนทำงาน",
      title: "รูปแบบ SDK เดียว ทุก operation อยู่ในที่ที่คาดไว้",
      intro: "ทำ integration ทุกครั้งด้วยสามขั้นตอนเดิม code preview อยู่ใกล้กับเรื่องราว เพื่อให้หน้านี้สอนการใช้งานได้จริง ไม่ได้แค่บอกคุณสมบัติ",
      steps: [
        { number: "01", label: "INPUT", title: "ติดตั้ง client", detail: "เพิ่ม Composer package เดียวเข้าไปใน PHP application ที่คุณใช้อยู่" },
        { number: "02", label: "SIGN", title: "เก็บ credentials ฝั่ง server", detail: "ตั้ง app keys, secrets และ tokens ครั้งเดียว request layer จะจัดการส่วนที่เหลือ" },
        { number: "03", label: "SHIP", title: "เรียก resource ที่ต้องการ", detail: "ไปต่อจาก authorization สู่ orders, logistics, finance หรือ surface ที่รองรับ" },
      ],
      fileName: "quick-start.php",
      language: "PHP",
      footer: "ค่า credentials จะอยู่ฝั่ง server เป็นค่าเริ่มต้น",
    },
    coverage: {
      kicker: "ขอบเขต resource",
      title: "ครอบคลุม commerce surface ทั้งหมดโดยไม่ต้องเจอ documentation กำแพงใหญ่",
      intro: "เริ่มจาก resource ที่แอปต้องใช้วันนี้ naming rhythm เดิมจะทำให้ integration ถัดไปคุ้นเคยตั้งแต่แรก",
      resources: [
        { index: "01", name: "Authorization", detail: "OAuth, shops, tokens และทางเข้าแอปที่ปลอดภัย" },
        { index: "02", name: "Products", detail: "Catalog, inventory และงานจัดการ listing" },
        { index: "03", name: "Orders", detail: "ดึง order และ workflow fulfillment" },
        { index: "04", name: "Logistics", detail: "ผู้ให้บริการขนส่ง tracking และ labels" },
        { index: "05", name: "Finance", detail: "Statements, settlements และ transactions" },
        { index: "06", name: "Returns", detail: "Returns, refunds และ reverse logistics" },
        { index: "07", name: "Warehouse", detail: "การจัดการคลังและสต็อก" },
        { index: "08", name: "Video", detail: "งานจัดการวิดีโอและคอนเทนต์" },
        { index: "09", name: "Global", detail: "operation ข้ามตลาดของ platform" },
      ],
      ribbon: [
        { title: "AUTH", detail: "credentials" },
        { title: "REQUEST", detail: "resource client" },
        { title: "RESPONSE", detail: "แอปของคุณ" },
      ],
    },
    cta: {
      kicker: "พร้อม ship แล้ว",
      title: "ให้ commerce layer ของคุณมีศูนย์กลางที่ชัดเจนขึ้น",
      body: "ติดตั้ง package เพิ่ม credentials และทำ resource call แรกได้วันนี้",
      github: "เปิดบน GitHub",
      terms: "อ่านข้อกำหนด",
    },
    footer: {
      description: "PHP SDK อย่างไม่เป็นทางการสำหรับ TikTok Shop Open Platform",
      setup: "เริ่มต้นใช้งาน",
      source: "ซอร์สโค้ด",
      privacy: "ความเป็นส่วนตัว",
      terms: "ข้อกำหนด",
    },
  },
  privacy: {
    meta: { title: "นโยบายความเป็นส่วนตัว — zTTShop", description: "นโยบายความเป็นส่วนตัวสำหรับเว็บไซต์ zTTShop PHP SDK" },
    kicker: "กฎหมาย · ความเป็นส่วนตัว",
    title: "นโยบายความเป็นส่วนตัว",
    intro: "ข้อมูลถูกจัดการอย่างไรเมื่อคุณเข้าชมเว็บไซต์ zTTShop หรือใช้งาน PHP SDK แบบโอเพนซอร์ส",
    effective: "มีผลบังคับใช้ 2 สิงหาคม 2026",
    indexLabel: "เนื้อหาในหน้านี้",
    backToHome: "กลับหน้าแรก",
    sections: [
      { id: "overview", number: "01", title: "ภาพรวม", body: "zTTShop คือ PHP SDK แบบโอเพนซอร์สที่ไม่เป็นทางการสำหรับเชื่อมต่อ TikTok Shop Open Platform เว็บไซต์นี้ให้ข้อมูลผลิตภัณฑ์ คำแนะนำการติดตั้ง และลิงก์ไปยังซอร์สโค้ดของโครงการ เว็บไซต์นี้ไม่ได้ดำเนินการโดย ไม่ได้เป็นพันธมิตร หรือได้รับการรับรองจาก TikTok" },
      { id: "information", number: "02", title: "ข้อมูลที่เราประมวลผล", body: "เว็บไซต์นี้ไม่ขอให้คุณสร้างบัญชี และไม่เก็บ credentials ของ TikTok Shop, API keys, access tokens, ข้อมูลการชำระเงิน หรือข้อมูลคำสั่งซื้อของลูกค้า โครงสร้างพื้นฐานสำหรับโฮสต์อาจประมวลผลข้อมูลทางเทคนิคที่จำเป็นอย่างจำกัด เช่น IP address ประเภทเบราว์เซอร์และอุปกรณ์ หน้าที่ร้องขอ เวลา และ security logs" },
      { id: "use", number: "03", title: "เราใช้ข้อมูลอย่างไร", body: "ข้อมูลทางเทคนิคอาจใช้เพื่อให้เว็บไซต์ทำงาน รักษาความพร้อมใช้งาน ตรวจสอบข้อผิดพลาด ป้องกันการใช้งานในทางที่ผิด และทำความเข้าใจการใช้งานในภาพรวม เราไม่ขายข้อมูลส่วนบุคคลและไม่ใช้เว็บไซต์นี้เพื่อสร้างโปรไฟล์โฆษณา" },
      { id: "sharing", number: "04", title: "ผู้ให้บริการและลิงก์ภายนอก", body: "ผู้ให้บริการโครงสร้างพื้นฐานอาจประมวลผลข้อมูลทางเทคนิคเพื่อโฮสต์ รักษาความปลอดภัย และส่งมอบเว็บไซต์เท่านั้น ลิงก์ไปยัง GitHub, Composer/Packagist, TikTok หรือบริการภายนอกอื่นอยู่ภายใต้นโยบายความเป็นส่วนตัวของบริการนั้น" },
      { id: "security", number: "05", title: "ความปลอดภัยของ SDK", body: "เก็บ app secrets และ tokens ไว้ใน server-side environment variables อย่า commit credentials ลง source control หรือเปิดเผยให้ browser เห็น คุณมีหน้าที่รับผิดชอบ access controls, retention rules และมาตรการป้องกันในแอปที่สร้างด้วย SDK" },
      { id: "rights", number: "06", title: "การเก็บรักษาและสิทธิของคุณ", body: "Operational logs จะถูกเก็บเท่าที่จำเป็นอย่างสมเหตุสมผลต่อความปลอดภัยและการให้บริการ ทั้งนี้ขึ้นอยู่กับสถานที่ของคุณ คุณอาจมีสิทธิขอเข้าถึง แก้ไข ลบ จำกัด หรือคัดค้านการประมวลผลข้อมูลส่วนบุคคล" },
      { id: "changes", number: "07", title: "การเปลี่ยนแปลงนโยบาย", body: "เราอาจอัปเดตนโยบายนี้เมื่อเว็บไซต์ โฮสติ้ง หรือข้อกำหนดทางกฎหมายเปลี่ยนแปลง วันที่มีผลบังคับใช้ด้านบนจะแสดงเวอร์ชันปัจจุบัน" },
      { id: "contact", number: "08", title: "ติดต่อ", body: "หากมีคำถามเรื่องความเป็นส่วนตัว ให้เปิด issue ใน", link: { href: "https://github.com/cvsz/zttshop-php/issues", label: "zTTShop GitHub repository", suffix: " อย่าใส่ credentials, tokens, ข้อมูลลูกค้า หรือข้อมูลสำคัญใน public issue" } },
    ],
  },
  terms: {
    meta: { title: "ข้อกำหนดการใช้งาน — zTTShop", description: "ข้อกำหนดสำหรับการใช้เว็บไซต์และ PHP SDK ของ zTTShop" },
    kicker: "กฎหมาย · ข้อกำหนด",
    title: "ข้อกำหนดการใช้งาน",
    intro: "ข้อกำหนดสำหรับการเข้าถึงเว็บไซต์นี้และการใช้งาน PHP SDK แบบโอเพนซอร์สของ zTTShop",
    effective: "มีผลบังคับใช้ 2 สิงหาคม 2026",
    indexLabel: "เนื้อหาในหน้านี้",
    backToHome: "กลับหน้าแรก",
    sections: [
      { id: "acceptance", number: "01", title: "การยอมรับ", body: "เมื่อเข้าถึงเว็บไซต์นี้หรือใช้ zTTShop SDK คุณตกลงตามข้อกำหนดเหล่านี้ หากไม่ยอมรับ โปรดอย่าใช้เว็บไซต์หรือซอฟต์แวร์ คุณต้องมีความสามารถตามกฎหมายในการยอมรับข้อกำหนดและมีอำนาจดำเนินการแทนองค์กรที่ระบบของคุณจะเชื่อมต่อ" },
      { id: "license", number: "02", title: "ไลเซนส์โอเพนซอร์ส", body: "ซอร์สโค้ดของ SDK เผยแพร่ภายใต้ MIT License สิทธิในการใช้ คัดลอก แก้ไข รวม เผยแพร่ แจกจ่าย ให้สิทธิช่วง หรือขายสำเนา อยู่ภายใต้ไลเซนส์และประกาศลิขสิทธิ์ดังกล่าว" },
      { id: "platform", number: "03", title: "กฎของ TikTok Shop platform", body: "zTTShop เป็นโครงการอย่างไม่เป็นทางการและไม่มีความเกี่ยวข้องหรือได้รับการรับรองจาก TikTok แอปและการใช้งาน API ของคุณต้องปฏิบัติตามข้อตกลง TikTok Shop Open Platform, developer policies, rate limits, กฎการค้า และกฎหมายที่เกี่ยวข้อง" },
      { id: "credentials", number: "04", title: "ระบบและ credentials ของคุณ", body: "คุณรับผิดชอบ app approval, credentials, วงจรชีวิต token, scopes ที่ร้องขอ, shop authorization, ความถูกต้องของข้อมูล และการกระทำผ่าน integration ของคุณ ปกป้อง secrets ใช้สิทธิ์เท่าที่จำเป็น ตรวจสอบ webhooks และเพิกถอน credentials ที่ถูกโจมตี" },
      { id: "conduct", number: "05", title: "การใช้งานที่ยอมรับได้", body: "คุณต้องไม่ใช้เว็บไซต์หรือ SDK เพื่อฝ่าฝืนกฎหมาย นโยบาย platform สิทธิความเป็นส่วนตัวหรือลิขสิทธิ์ เผยแพร่ malware เข้าถึงระบบโดยไม่ได้รับอนุญาต บิดเบือนธุรกรรม หรือรบกวนบริการอื่น" },
      { id: "disclaimer", number: "06", title: "ไม่มีการรับประกัน", body: "เว็บไซต์และ SDK ให้บริการตามสภาพที่เป็นอยู่และตามที่มีให้บริการ โดยไม่มีการรับประกันใด ๆ เราไม่รับประกันความพร้อมใช้งานต่อเนื่อง ความเข้ากันได้กับ API ทุกเวอร์ชัน การทำงานที่ปราศจากข้อผิดพลาด หรือความเหมาะสมต่อวัตถุประสงค์ทางการค้าเฉพาะ" },
      { id: "liability", number: "07", title: "ข้อจำกัดความรับผิด", body: "ภายใต้ขอบเขตสูงสุดที่กฎหมายอนุญาต ผู้มีส่วนร่วมในโครงการจะไม่รับผิดต่อความเสียหายทางอ้อม โดยบังเอิญ พิเศษ เป็นผลสืบเนื่อง เป็นตัวอย่าง หรือเป็นโทษ รวมถึงกำไร ข้อมูล รายได้ goodwill orders หรือโอกาสทางธุรกิจที่สูญเสีย" },
      { id: "changes", number: "08", title: "การเปลี่ยนแปลงและความพร้อมใช้งาน", body: "เราอาจแก้ไขเว็บไซต์ documentation SDK หรือข้อกำหนดเหล่านี้ได้ทุกเมื่อ การใช้งานต่อหลังวันที่มีผลของฉบับใหม่ถือเป็นการยอมรับข้อกำหนดที่แก้ไขแล้ว" },
      { id: "contact", number: "09", title: "ติดต่อ", body: "หากต้องการความช่วยเหลือหรือมีคำถามเกี่ยวกับข้อกำหนด ให้ใช้", link: { href: "https://github.com/cvsz/zttshop-php/issues", label: "GitHub issue tracker", suffix: " ห้ามโพสต์ credentials, ข้อมูลส่วนบุคคล หรือข้อมูล commerce ที่เป็นความลับต่อสาธารณะ" } },
    ],
  },
};

export const messages: Record<Locale, Dictionary> = { en, th };

export function getDictionary(locale: Locale): Dictionary {
  return messages[locale];
}
