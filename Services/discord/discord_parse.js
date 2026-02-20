// noinspection JSUnresolvedReference

import {parse} from "discord-markdown-parser";

function preprocessMessage(input) {
    // Convert Discord's special link format: [@username](<url>) -> username (no @)
    input = input.replace(/\[@([^\]]+)]\(<([^>]+)>\)/g, '$1');
    // Convert Discord's channel link format: [#channel](<url>) -> #channel
    input = input.replace(/\[#([^\]]+)]\(<[^>]+>\)/g, '#$1');
    // Convert other Markdown links: [text](<url>) -> text(url) or [text](url) -> text(url)
    input = input.replace(/\[([^\]]+)]\(<([^>]+)>\)/g, '$1($2)');
    input = input.replace(/\[([^\]]+)]\(([^)]+)\)/g, '$1($2)');
    return input;
}

function render(nodes) {
    let out = "";

    for (const n of nodes) {
        switch (n.type) {
            case "text":
                out += n.content;
                break;

            case "newline":
            case "br":
                out += "\n";
                break;

            case "timestamp":
                const ts = Number(n.timestamp) * 1000;
                const date = new Date(ts);
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                const fullString = `${year}-${month}-${day} ${hours}:${minutes}`
                out += out.includes(fullString) ? '' : fullString;
                break;

            case "mention":
            case "emoji":
                break;

            case "link":
            case "autolink":
                if (n.content) {
                    out += render(n.content);
                }
                if (n.target) {
                    out += `(${n.target})`;
                }
                break;

            case "url":
                // Keep bare URLs as-is
                if (n.target) {
                    out += n.target;
                }
                break;

            case "channel":
                out += "#" + (n.name ?? "channel");
                break;

            default:
                if (n.content) {
                    out += render(n.content);
                }
                break;
        }
    }

    return out;
}

const input = process.argv[2];
if (!input) {
    console.error("No input provided");
    process.exit(1);
}

try {
    const preprocessed = preprocessMessage(input);
    const ast = parse(preprocessed, "normal");
    const result = render(ast);
    console.log(result);
} catch (err) {
    console.error("Parse error:", err.message);
    console.error(err.stack);
    process.exit(1);
}

