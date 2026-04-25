export interface ParamDoc {
  key: string;
  title: string;
  type: string;
  desc: string;
  example: string;
}

export const PARAM_DOCS: ParamDoc[] = [
  {
    key: "input_docx_path",
    title: "input_docx_path",
    type: "string",
    desc: "Абсолютный путь к исходному файлу отчёта в формате .docx. Вставляйте путь как есть.\n\n⚠ Windows: в данный момент поддерживается только диск P:\\. Пути на других дисках (C:\\, D:\\ и др.) и сетевые пути (\\\\server\\...) не поддерживаются.\n\nLinux: любой абсолютный путь принимается без изменений.",
    example: "input_docx_path: P:\\WP13C\\report.docx",
  },
  {
    key: "output_dir",
    title: "output_dir",
    type: "string",
    desc: "Папка, куда будут сохранены результаты проверки. Создаётся автоматически, если не существует. Вставляйте путь как есть.\n\n⚠ Windows: в данный момент поддерживается только диск P:\\.\n\nПо умолчанию: Windows — P:\\temp\\report_check_results\\, Linux — /filer/wps/wp/temp/report_check_results",
    example: "output_dir: P:\\temp\\report_check_results\\",
  },
  {
    key: "subchapters_range",
    title: "subchapters_range",
    type: "string (необязательно)",
    desc: "Диапазон подразделов для проверки. Пустая строка = проверить все. Формат: «1-3, 5» означает разделы 1, 2, 3 и 5.",
    example: 'subchapters_range: "1-3, 5"',
  },
  {
    key: "chunk_size_tokens",
    title: "chunk_size_tokens",
    type: "integer",
    desc: "Максимальный размер одного чанка текста в токенах, передаваемого в модель. Увеличьте для длинных разделов, уменьшите при ошибках context length.\n\nВерхний предел задаётся переменной окружения MAX_CHUNK_TOKENS (по умолчанию 15 000).",
    example: "chunk_size_tokens: 3000",
  },
  {
    key: "temperature",
    title: "temperature",
    type: "float | null",
    desc: "Температура генерации модели (0.0–2.0). null = используется значение по умолчанию модели. Меньше = детерминированнее.",
    example: "temperature: null",
  },
  {
    key: "check_prompt",
    title: "check_prompt",
    type: "string (многострочный)",
    desc: "Основной промпт для проверки раздела. Используйте блочный скалярный синтаксис YAML (символ | после двоеточия). Переносы строк сохраняются.",
    example: "check_prompt: |\n  Вы — строгий рецензент.\n  Проверьте раздел по критериям...",
  },
  {
    key: "validation_prompt",
    title: "validation_prompt",
    type: "string (необязательно)",
    desc: "Промпт для этапа валидации результатов проверки. Пустая строка — этап пропускается.",
    example: 'validation_prompt: ""',
  },
  {
    key: "summary_prompt",
    title: "summary_prompt",
    type: "string (необязательно)",
    desc: "Промпт для финального суммирования. Пустая строка — этап пропускается.",
    example: 'summary_prompt: ""',
  },
];
