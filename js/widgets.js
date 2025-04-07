import {
  MosaicClient,
  clausePoint,
  Param,
  isParam,
  isSelection,
  toDataColumns,
} from "https://cdn.jsdelivr.net/npm/@uwdata/mosaic-core@0.15.0/+esm";

import {
  Query,
  column,
} from "https://cdn.jsdelivr.net/npm/@uwdata/mosaic-sql@0.15.0/+esm";

import * as vg from "https://cdn.jsdelivr.net/npm/@uwdata/vgplot@0.15.0/+esm";

class FiltersClient extends MosaicClient {
  constructor(filterBy) {
    super(filterBy);
    this.element = document.createElement("div");
  }

  update() {
    console.log("update", this._filterBy, this._filterBy.clauses);

    this.redraw();

    return this;
  }

  redraw() {
    this.element.replaceChildren();
    let h3 = document.createElement("h3");
    h3.innerText = "Filters";
    this.element.appendChild(h3);
    this._filterBy.clauses.forEach((c) => {
      console.log("clause", c);
      let s = document.createElement("div");
      s.innerText = c.predicate._expr[0];
      s.addEventListener("click", (e) => {
        console.log("clicked on", c);
        let clause = {
          ...c,
          value: undefined,
          predicate: null,
        };
        this._filterBy.update(clause);
      });
      this.element.appendChild(s);
    });
  }

  query(filter = []) {
    console.log("query", filter, this._filterBy);
    return Query.from("data").select({ c: vg.count() });
  }
}

const isObject = (v) => {
  return v && typeof v === "object" && !Array.isArray(v);
};

class MultiMenu extends MosaicClient {
  /**
   * Create a new menu input.
   * @param {object} [options] Options object
   * @param {HTMLElement} [options.element] The parent DOM element in which to
   *  place the menu elements. If undefined, a new `div` element is created.
   * @param {Selection} [options.filterBy] A selection to filter the database
   *  table indicated by the *from* option.
   * @param {Param} [options.as] The output param or selection. A selection
   *  clause is added for the currently selected menu option.
   * @param {string} [options.field] The database column name to use within
   *  generated selection clause predicates. Defaults to the *column* option.
   * @param {(any | { value: any, label?: string })[]} [options.options] An
   *  array of menu options, as literal values or option objects. Option
   *  objects have a `value` property and an optional `label` property. If no
   *  label or *format* function is provided, the string-coerced value is used.
   * @param {(value: any) => string} [options.format] A format function that
   *  takes an option value as input and generates a string label. The format
   *  function is not applied when an explicit label is provided in an option
   *  object.
   * @param {*} [options.value] The initial selected menu value.
   * @param {string} [options.from] The name of a database table to use as a data
   *  source for this widget. Used in conjunction with the *column* option.
   * @param {string} [options.column] The name of a database column from which
   *  to pull menu options. The unique column values are used as menu options.
   *  Used in conjunction with the *from* option.
   * @param {string} [options.label] A text label for this input.
   */
  constructor({
    element,
    filterBy,
    from,
    column,
    label = column,
    format = (x) => x, // TODO
    options,
    value,
    field = column,
    as,
  } = {}) {
    super(filterBy);
    this.from = from;
    this.column = column;
    this.format = format;
    this.field = field;
    const selection = (this.selection = as);

    this.element = element ?? document.createElement("div");
    this.element.setAttribute("class", "input");
    Object.defineProperty(this.element, "value", {
      value: this,
    });

    const lab = document.createElement("label");
    lab.innerText = label || column;
    this.element.appendChild(lab);

    this.select = document.createElement("select");
    this.select.setAttribute("multiple", "true");
    this.element.appendChild(this.select);

    // if provided, populate menu options
    if (options) {
      this.data = options.map((value) => (isObject(value) ? value : { value }));
      this.selectedValue(value ?? "");
      this.update();
    }

    // initialize selection or param bindings
    if (selection) {
      const isParam = !isSelection(selection);

      // publish any initial menu value to the selection/param
      // later updates propagate this back to the menu element
      // do not publish if using a param that already has a value
      if (value != null && (!isParam || selection.value === undefined)) {
        this.publish(value);
      }

      // publish selected value upon menu change
      this.select.addEventListener("input", () => {
        this.publish(this.selectedValue() ?? null);
      });

      // if bound to a scalar param, respond to value updates
      if (isParam) {
        this.selection.addEventListener("value", (value) => {
          if (value !== this.select.value) {
            this.selectedValue(value);
          }
        });
      }
    }
  }

  selectedValue(value) {
    if (arguments.length === 0) {
      const index = this.select.selectedIndex;
      return this.data[index].value;
    } else {
      const index = this.data?.findIndex((opt) => opt.value === value);
      if (index >= 0) {
        this.select.selectedIndex = index;
      } else {
        this.select.value = String(value);
      }
    }
  }

  reset() {
    this.select.selectedIndex = this.from ? 0 : -1;
  }

  publish(value) {
    const { selection, field } = this;
    if (isSelection(selection)) {
      if (value === "") value = undefined; // 'All' option
      const clause = clausePoint(field, value, {
        source: this,
      });
      selection.update(clause);
    } else if (isParam(selection)) {
      selection.update(value);
    }
  }

  query(filter = []) {
    const { from, column } = this;
    if (!from) return null;
    return Query.from(from)
      .select({ value: column })
      .distinct()
      .where(filter)
      .orderby(column);
  }

  queryResult(data) {
    // column option values, with an inserted 'All' value
    this.data = [{ value: "", label: "All" }, ...data];
    return this;
  }

  update() {
    const { data, format, select, selection } = this;

    // generate menu item options
    select.replaceChildren();
    for (const { value, label } of data) {
      const opt = document.createElement("option");
      opt.setAttribute("value", value);
      opt.innerText = label ?? format(value);
      this.select.appendChild(opt);
    }

    // update menu value based on param/selection
    if (selection) {
      const value = isSelection(selection)
        ? selection.valueFor(this)
        : selection.value;
      this.selectedValue(value ?? "");
    }

    return this;
  }
}

function input(InputClass, options) {
  const input = new InputClass(options);
  vg.coordinator().connect(input);
  return input.element;
}

const multimenu = (options) => input(MultiMenu, options);

export { FiltersClient, MultiMenu, multimenu };
