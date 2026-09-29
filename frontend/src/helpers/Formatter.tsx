//format thosands with comma
export const formatThousands = (value: number | string): string => {
    const num = typeof value === "string" ? parseFloat(value) : value;
    if (isNaN(num)) return "";
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
};

// Allow only numbers/digits, hyphen (-), and backspace (8) for date input
export const isDate = (evt: KeyboardEvent): boolean => {
    const charCode = evt.which ? evt.which : (evt as any).keyCode;
    if ((charCode >= 48 && charCode <= 57) || charCode === 45 || charCode === 8) {
        return true;
    }
    return false;
};

// Allow only numbers/digits, decimal point (.), and backspace (8) for percentage input
export const isPercentage = (evt: KeyboardEvent): boolean => {
    const charCode = evt.which ? evt.which : (evt as any).keyCode;
    if ((charCode >= 48 && charCode <= 57) || charCode === 46 || charCode === 8) {
        return true;
    }
    return false;
};

// Allow only numbers/digits in input
export const isNumberKey = (evt: KeyboardEvent): boolean => {
    const charCode = evt.which ? evt.which : (evt as any).keyCode;
    if (charCode > 31 && (charCode < 48 || charCode > 57)) {
        return false;
    }
    return true;
};

// Allow only numbers/digits and letters in input
export const isNumberLetterKey = (evt: KeyboardEvent): boolean => {
    const charCode = evt.which ? evt.which : (evt as any).keyCode;
    if (
        (charCode >= 48 && charCode <= 57) || 
        (charCode >= 65 && charCode <= 90) || 
        (charCode >= 97 && charCode <= 122) || 
        charCode === 8 || 
        charCode === 32
    ) {
        return true;
    }
    return false;
};

// Allow only alphabets & space
export const isLetterKey = (key: KeyboardEvent): boolean => {
    const keycode = key.which ? key.which : (key as any).keyCode;
    if ((keycode > 64 && keycode < 91) || (keycode > 96 && keycode < 123) || keycode === 32) {
        return true;
    } else {
        return false;
    }
};

// Allow alphabet, number, comma, period, and space
export const isWithoutSlash = (key: KeyboardEvent): boolean => {
    const keycode = key.which ? key.which : (key as any).keyCode;
    if (
        (keycode >= 48 && keycode <= 57) || 
        (keycode >= 65 && keycode <= 90) || 
        (keycode >= 97 && keycode <= 122) || 
        keycode === 8 || 
        keycode === 44 || 
        keycode === 46 || 
        keycode === 32
    ) {
        return true;
    } else {
        return false;
    }
};

// Allow alphabet, number, comma, period, forward slash, and space
export const isWithSlash = (key: KeyboardEvent): boolean => {
    const keycode = key.which ? key.which : (key as any).keyCode;
    if (
        (keycode >= 48 && keycode <= 57) || 
        (keycode >= 65 && keycode <= 90) || 
        (keycode >= 97 && keycode <= 122) || 
        keycode === 8 || 
        keycode === 44 || 
        keycode === 46 || 
        keycode === 47 || 
        keycode === 32
    ) {
        return true;
    } else {
        return false;
    }
};

// Validate ID card input based on citizenship
export const validateIDCard = (evt: KeyboardEvent, citizenship: string): boolean => {
    const charCode = evt.which ? evt.which : (evt as any).keyCode;
    if (citizenship === 'ID') {
        if (charCode > 31 && (charCode < 48 || charCode > 57)) {
            return false;
        } else {
            return true;
        }
    } else {
        if (
            (charCode >= 48 && charCode <= 57) || 
            (charCode >= 65 && charCode <= 90) || 
            (charCode >= 97 && charCode <= 122) || 
            charCode === 8 || 
            charCode === 32 || 
            charCode === 45
        ) {
            return true;
        } else {
            return false;
        }
    }
};

export default {
    formatThousands,
    isDate,
    isPercentage,
    isNumberKey,
    isNumberLetterKey,
    isLetterKey,
    isWithoutSlash,
    isWithSlash,
    validateIDCard
};