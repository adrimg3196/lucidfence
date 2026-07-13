/* reicon — Free Open-Source Icon Library (github.com/dqev/reicon)
 * Vanilla-JS adapter. Renders real reicon SVG paths (Outline / Filled weights)
 * into a string, matching the upstream `createIcon.toSvg()` contract.
 * Data is provided by static/reicon-data.js (window.REICON_DATA).
 *
 * Usage:
 *   reicon("map")                                  -> 24px Outline SVG
 *   reicon("alert-triangle2", {weight:"Filled"})   -> Filled SVG
 *   reicon("shield", {size:18, color:"#ef4444"})   -> colored SVG
 */
(function (global) {
  "use strict";

  var W_MAP = { Filled: "Filled", Outline: "Outline" };

  function escAttr(v) {
    return String(v)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function reicon(name, options) {
    options = options || {};
    var data = (global.REICON_DATA && global.REICON_DATA.icons) || {};
    var icon = data[name];
    if (!icon) {
      // Fallback: a neutral dot so the layout never breaks.
      return '<svg xmlns="http://www.w3.org/2000/svg" width="' +
        (options.size || 24) + '" height="' + (options.size || 24) +
        '" viewBox="0 0 24 24" fill="none" class="reicon"><circle cx="12" cy="12" r="5" fill="currentColor"/></svg>';
    }
    var color = options.color || "currentColor";
    var size = options.size || 24;
    var weight = options.weight || "Outline";
    var strokeWidth = options.strokeWidth;
    var className = options.className;
    var attrs = options.attrs || {};

    var key = W_MAP[weight] || "Outline";
    var weights = icon.weights || {};
    var firstKey = Object.keys(weights)[0] || "";
    var entry = weights[key] || (firstKey ? weights[firstKey] : "") || "";
    var html = (entry && typeof entry === "object" && entry.code != null) ? entry.code : String(entry || "");

    if (strokeWidth != null) {
      html = html.replace(/stroke-width="[^"]*"/g, 'stroke-width="' + strokeWidth + '"');
    }

    var extra = Object.keys(attrs)
      .map(function (k) { return " " + escAttr(k) + '="' + escAttr(attrs[k]) + '"'; })
      .join("");

    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + escAttr(size) +
      '" height="' + escAttr(size) + '" viewBox="0 0 24 24" fill="none" class="' +
      escAttr(className ? "reicon " + className : "reicon") + '" style="color: ' +
      escAttr(color) + '"' + (extra ? extra : "") + ">" + html + "</svg>";
  }

  // Convenience: returns the raw inner SVG markup for a name (for inline composition).
  reicon.path = function (name, weight) {
    var data = (global.REICON_DATA && global.REICON_DATA.icons) || {};
    var icon = data[name];
    if (!icon) return "";
    var w = icon.weights || {};
    return w[weight === "Filled" ? "Filled" : "Outline"] || w[Object.keys(w)[0]] || "";
  };

  // List of available names (for debugging / autocomplete).
  reicon.names = function () {
    return Object.keys((global.REICON_DATA && global.REICON_DATA.icons) || {});
  };

  global.reicon = reicon;
})(typeof window !== "undefined" ? window : this);
