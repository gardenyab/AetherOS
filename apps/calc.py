class Calc:
    """тестовый калькулятор"""
    
    def calc(self, args):
        """пишет ок"""
        print("ok")

    def sum(self, args):
        """складывает числа"""
        try:
            result = sum(float(x) for x in args)
            print(f"Сумма: {result}")
        except ValueError:
            print("Ошибка: передавай только числа")