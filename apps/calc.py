class Calc:
    """Обычный калькулятор для вычислений"""
    
    def calc(self, args):
        """пишет ок"""
        print("ok")

    def sum(self, args):
        """складывает переданные числа"""
        try:
            result = sum(float(x) for x in args)
            print(f"Сумма: {result}")
        except ValueError:
            print("Ошибка: передавай только числа")