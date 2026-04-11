/**
 * cart.js
 * -------
 * Shopping cart module — cAST chunking example.
 */

const TAX_RATE = 0.08;

/**
 * Represents a single item in the shopping cart.
 */
class CartItem {
    constructor(productId, name, price, quantity = 1) {
        this.productId = productId;
        this.name = name;
        this.price = price;
        this.quantity = quantity;
    }

    get lineTotal() {
        return parseFloat((this.price * this.quantity).toFixed(2));
    }

    toJSON() {
        return {
            productId: this.productId,
            name:      this.name,
            price:     this.price,
            quantity:  this.quantity,
            lineTotal: this.lineTotal,
        };
    }
}

/**
 * Manages a collection of CartItems and exposes pricing helpers.
 */
class ShoppingCart {
    constructor(taxRate = TAX_RATE) {
        this._items = new Map();
        this.taxRate = taxRate;
    }

    addItem(item) {
        if (!(item instanceof CartItem)) {
            throw new TypeError("Expected a CartItem instance");
        }
        if (this._items.has(item.productId)) {
            this._items.get(item.productId).quantity += item.quantity;
        } else {
            this._items.set(item.productId, item);
        }
        return this;
    }

    removeItem(productId) {
        return this._items.delete(productId);
    }

    get subtotal() {
        let total = 0;
        for (const item of this._items.values()) {
            total += item.lineTotal;
        }
        return parseFloat(total.toFixed(2));
    }

    get tax() {
        return parseFloat((this.subtotal * this.taxRate).toFixed(2));
    }

    get total() {
        return parseFloat((this.subtotal + this.tax).toFixed(2));
    }

    clear() {
        this._items.clear();
    }

    toJSON() {
        return {
            items:    [...this._items.values()].map(i => i.toJSON()),
            subtotal: this.subtotal,
            tax:      this.tax,
            total:    this.total,
        };
    }
}

/**
 * Calculate discount given a promo code.
 * @param {string} code
 * @param {number} subtotal
 * @returns {number} discount amount
 */
function calculateDiscount(code, subtotal) {
    const discounts = { SAVE10: 0.10, SAVE20: 0.20, HALFOFF: 0.50 };
    const rate = discounts[code.toUpperCase()] ?? 0;
    return parseFloat((subtotal * rate).toFixed(2));
}

/**
 * Format a cart summary as a plain-text string.
 */
const formatCartSummary = (cart) => {
    const lines = ["===== Cart Summary ====="];
    for (const item of Object.values(cart.toJSON().items)) {
        lines.push(`  ${item.name} x${item.quantity} @ $${item.price} = $${item.lineTotal}`);
    }
    lines.push(`  Subtotal : $${cart.subtotal}`);
    lines.push(`  Tax      : $${cart.tax}`);
    lines.push(`  TOTAL    : $${cart.total}`);
    return lines.join("\n");
};

module.exports = { CartItem, ShoppingCart, calculateDiscount, formatCartSummary };
