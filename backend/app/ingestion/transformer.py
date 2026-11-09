class DataTransformer:
    @staticmethod
    def transform(dataframe, mapping):
        renamed = dataframe.rename(columns=mapping)

        final_columns = [
            col
            for col in [
                "descricao",
                "data",
                "responsavel",
            ]
            if col in renamed.columns
        ]

        return renamed[final_columns]
