import { CKEditor } from "@ckeditor/ckeditor5-react";
import {
    ClassicEditor,
    Essentials,
    Paragraph,
    Heading,
    Bold,
    Italic,
    Strikethrough,
    RemoveFormat,
    List,
    Indent,
    IndentBlock,
    BlockQuote,
    Link,
    Bookmark,
    Table,
    TableToolbar,
    TableProperties,
    TableCellProperties,
    ShowBlocks,
    SpecialCharacters,
    SpecialCharactersEssentials,
    SourceEditing,
    Style,
    GeneralHtmlSupport,
    Fullscreen,
    PasteFromOffice,
} from "ckeditor5";
import "ckeditor5/ckeditor5.css";

const CKEDITOR_LICENSE_KEY = "GPL";

const EDITOR_CONFIG = {
    licenseKey: CKEDITOR_LICENSE_KEY,
    plugins: [
        Essentials,
        Paragraph,
        Heading,
        Bold,
        Italic,
        Strikethrough,
        RemoveFormat,
        List,
        Indent,
        IndentBlock,
        BlockQuote,
        Link,
        Bookmark,
        Table,
        TableToolbar,
        TableProperties,
        TableCellProperties,
        ShowBlocks,
        SpecialCharacters,
        SpecialCharactersEssentials,
        SourceEditing,
        Style,
        GeneralHtmlSupport,
        Fullscreen,
        PasteFromOffice,
    ],
    toolbar: {
        items: [
            "undo", "redo", "|",
            "link", "bookmark", "|",
            "insertTable", "|",
            "showBlocks", "|",
            "specialCharacters", "|",
            "fullscreen", "|",
            "sourceEditing", "|",
            "bold", "italic", "strikethrough", "removeFormat", "|",
            "numberedList", "bulletedList", "|",
            "outdent", "indent", "|",
            "blockQuote", "|",
            "style", "|",
            "heading",
        ],
        shouldNotGroupWhenFull: true,
    },
    table: {
        contentToolbar: ["tableColumn", "tableRow", "mergeTableCells", "tableProperties", "tableCellProperties"],
    },
    style: {
        definitions: [
            { name: "Highlighted", element: "span", classes: ["highlight"] },
            { name: "Info box", element: "p", classes: ["info-box"] },
        ],
    },
};

export interface CKEditorNotesProps {
    value: string;
    onChange: (value: string) => void;
    minHeight?: number;
    className?: string;
}

export default function CKEditorNotes({ value, onChange, minHeight = 300, className = "" }: CKEditorNotesProps) {
    return (
        <div
            className={`ckeditor-notes rounded-lg border border-slate-300 overflow-hidden ${className}`}
            style={{ ["--ckeditor-notes-min-height" as any]: `${minHeight}px` }}
        >
            <style>{`
                .ckeditor-notes .ck-editor__editable_inline {
                    min-height: var(--ckeditor-notes-min-height, 300px);
                }
                .ckeditor-notes .ck-content .highlight {
                    background-color: #fef08a;
                    padding: 0 2px;
                }
                .ckeditor-notes .ck-content .info-box {
                    background-color: #eff6ff;
                    border-left: 3px solid #3b82f6;
                    padding: 8px 12px;
                    margin: 8px 0;
                }
            `}</style>
            <CKEditor
                editor={ClassicEditor}
                data={value}
                config={EDITOR_CONFIG}
                onChange={(_event, editor) => onChange(editor.getData())}
            />
        </div>
    );
}